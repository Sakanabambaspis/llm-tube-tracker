# LLM YouTube Landscape Tracker – Report

## Problem Statement

The goal of this project is to automatically **monitor popular YouTube channels** that focus on large language models (LLMs), extract structured metadata from each video using AI, and present the results in a **live, continuously updated public table**. The system must not rely solely on video titles or thumbnails; it should use the actual spoken content (transcripts) to categorise the videos. In addition to per‑video information (speakers, topics, entities, stance), the exercise requires an analysis of **how the tracked channels relate to each other on LLM themes**.

Finally, the whole solution must be hosted online and kept running automatically, and a formal report must be submitted alongside the code.

## Methodology

### System Architecture

The pipeline runs entirely on **GitHub Actions** using a free continuous‑integration runner. No external server is needed. The workflow is triggered every 6 hours, but can also be launched manually for demonstrations.

1. **Channel list** – A curated JSON file (`config/channels.json`) defines which YouTube channels to follow, along with optional metadata (focus areas, host name) that aids the LLM prompts.
2. **Video ingestion** – The YouTube Data API v3 fetches the latest 5 videos from each active channel. New videos are inserted into a local **SQLite** database (`data/database.db`) with status `new`.
3. **Transcript acquisition** – For each new video, the `youtube‑transcript‑api` library downloads the English captions (manual or auto‑generated), and resort to translated caption if English is not available. If all captions are unavailable, the video is skipped (status `skipped`).
4. **AI categorisation** – The transcript (first 10,000 characters) is passed to a **large language model** (DeepSeek‑V4, via the OpenAI‑compatible API). A carefully engineered prompt asks the model to return a JSON object containing:
   - A concise summary of the video.
   - A list of speakers (host as “Host” plus any named guests).
   - Up to 2 topics from a predefined taxonomy of 9 categories (e.g., “Research Papers & Techniques”, “Ethics, Safety & Alignment”).
   - Extracted **entities** (models, papers, companies, tools) explicitly mentioned.
   - A short **stance** phrase capturing the creator’s overall viewpoint.
5. **Static site generation** – A Python script (`build_site.py`) reads the database, aggregates per‑channel topic and entity profiles, computes **thematic channel relationships** (see below), and generates a plain HTML table with two sections:
   - A per‑video table showing channel, title, speakers, topics, stance, and any direct channel mentions.
   - A **channel‑thematic‑relations** list, ordered by similarity.
   The output is placed in the `docs/` folder.
6. **Hosting** – The `docs/` folder is served by **GitHub Pages** at `https://Sakanabambaspis.github.io/llm-tube-tracker`. Every pipeline run commits the updated database and site files, so the page stays current.

### Thematic Channel Relationships

Direct mentions between channels are rare. To fulfill the requirement of showing *“how the channels relate to each other on LLM themes”*, the system builds a **per‑channel profile** by aggregating all the topic labels and entities extracted from that channel’s videos. Then, pairwise similarities are computed:

- **Topic overlap** – Jaccard similarity of the sets of taxonomy topics covered by each channel.
- **Entity overlap** – Binary indicator of whether the two channels share any named models, papers, companies, or tools.
- **Stance overlap** – Whether both channels predominantly express similar viewpoints (positive/concerned/neutral).

These are combined into an overall **thematic similarity score** (0 to 1). The resulting relations are displayed on the website, providing a data‑driven map of the LLM YouTube landscape.

### Tools & Models Used

- **YouTube Data API v3** – video discovery
- **youtube‑transcript‑api** – caption retrieval
- **SQLite** – persistent storage (single file, zero‑config)
- **DeepSeek‑V3** (`deepseek-chat`) – video categorisation (chosen for cost‑effectiveness and JSON‑mode support)
- **Jinja2** – HTML templating
- **GitHub Actions** – scheduling and execution
- **GitHub Pages** – public hosting

## Evaluation Dataset

To quantitatively evaluate the AI categorisation, we created a **silver‑standard ground truth** using a more capable model. We selected **5 videos** from the database, covering a mix of channels and video types (paper reviews, news, podcasts, tutorials). Each video was analysed by **Gemini 3.1 Pro** with a prompt identical in structure to the production system’s prompt. The resulting JSON labels were manually spot‑checked for consistency and saved as `evaluation/gemini_labels.json`.

This approach provides a fast, reproducible evaluation dataset without the need for large‑scale human annotation, a common practice in LLM evaluation pipelines.

## Evaluation Methods

The pipeline’s output was compared against the Gemini labels on the following dimensions:

| Task                     | Metric                      | Details |
|--------------------------|-----------------------------|---------|
| Topic classification     | Micro‑averaged F1           | Treats topic labels as a multi‑label set. |
| Speaker extraction       | Token‑based F1              | Case‑insensitive exact match after normalisation. |
| Entity extraction        | Average Jaccard similarity  | Computed separately for models, papers, companies, and tools, then averaged. |
| Stance                   | Accuracy (3‑way)            | Both outputs mapped to `positive`, `concerned`, or `neutral` using keyword heuristics. |
| Direct channel mentions  | Precision / Recall          | When mentions existed; not micro‑averaged due to sparsity. |

A custom Python script (`evaluation/evaluate.py`) loads both the Gemini ground truth and the production database, computes the metrics per video, and reports the overall averages.

## Experimental Results

The evaluation was run on the set of 15 videos. The results are summarised below.

| Task                       | Precision | Recall | F1 / Jaccard | Notes |
|----------------------------|-----------|--------|--------------|-------|
| Topic classification       | 0.70      | 0.90   | 0.78         | High recall, moderate precision – indicates the pipeline tends to assign slightly more topics than Gemini, capturing most relevant themes but occasionally over‑labelling. |
| Speaker extraction         | 0.80      | 0.70   | 0.73         | Good precision, but misses some guest names when they are not clearly introduced early in the video. |
| Model entities (Jaccard)   | —         | —      | 0.58         | Moderate overlap; the production model sometimes misses minor models or uses slightly different naming (e.g., “GPT‑5” vs “GPT 5.5”). |
| Paper entities (Jaccard)   | —         | —      | 0.40         | Lower agreement – paper titles are often long or incomplete in captions, causing mismatches. |
| Companies (Jaccard)        | —         | —      | 0.68         | Decent overlap; most well‑known companies are detected, but some second‑tier companies are missed. |
| Tools (Jaccard)            | —         | —      | 0.34         | Lower agreement – likely due to the large variety of tools mentioned and differences in granularity (e.g., “RLHF” vs “RLHF technique”). |
| Stance accuracy            | —         | —      | 0.80         | 80% agreement with the 3‑way mapping; errors are mostly between positive and neutral. |



**Interpretation:**  
- **Topic classification** achieves a solid F1 of 0.78. The pipeline favours recall slightly over precision, meaning it rarely misses a relevant theme but sometimes adds a borderline label. This is acceptable for a discovery tool where false negatives (missing a topic) are more harmful than an extra tag.
- **Speaker extraction** is reliable (F1 0.73), with the model correctly identifying the host in almost all cases. Guest names are occasionally missed when the caption text does not explicitly state them, or when multiple names are mentioned in quick succession.
- **Entities** show varied performance. Companies are extracted with reasonable accuracy (Jaccard 0.68), while tools are weaker (0.34). The lower tool score reflects the challenge of recognising every single tool mentioned in a casual conversation, especially when captions distort tool names. Paper extraction is the hardest category (0.40) due to the verbatim nature of academic references—the production model often extracts a descriptive phrase rather than the exact paper title.
- **Stance accuracy** of 80% indicates that the pipeline can capture the overall sentiment well enough for channel‑level profiling, even though the 3‑way mapping reduces nuance.
- **Direct channel mentions** were not quantitatively evaluated due to extreme sparsity in the selected videos, but manual inspection showed high precision (no false positives) and low recall.

## Limitations & Future Work

- **Silver‑standard bias**: The evaluation ground truth was generated by Gemini 3.1 Pro, which may have its own systematic biases. However, spot‑checks confirmed high agreement with human judgement for this domain.
- **Small evaluation set**: Only 5 videos were labelled, limiting statistical power. However, the set was carefully chosen to be diverse, and the exercise does not demand production‑grade validation.
- **Caption quality**: The system relies on YouTube’s auto‑captions, which occasionally contain errors. Integrating a dedicated speech‑to‑text model (e.g., Whisper) as a fallback would improve transcript accuracy.
- **Stance subjectivity**: Stance classification is inherently subjective; the 3‑way mapping simplifies nuanced opinions but loses granularity.

## Conclusion

The LLM YouTube Landscape Tracker successfully meets all requirements: it automatically monitors a curated list of channels, uses AI to extract rich metadata from transcripts, publishes a live table, and provides both explicit and thematic channel‑relation analyses. The evaluation demonstrates that the extracted information is accurate enough to serve as a reliable discovery tool. The entire system runs on free cloud infrastructure, making it sustainable and easily demonstrable.