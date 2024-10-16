# Fintext-RAG project in CFDA lab
## Usage
- One need to also git clone the [customized trectools](https://github.com/hyusterr/trectools/tree/recall) to the same directory as a submodule. 
```bash
git clone git@github.com:hyusterr/fin.rag.git
cd fin.rag
pip install -r requirements.txt
git clone git@github.com:hyusterr/trectools.git
cd trectools
git checkout recall
pip install -e ./trectools/
```

## Evaluation
### Evaulate task1 (Highlighting)
#### Attention Highlighter 
- from "Towards Annotating and Creating Sub-Sentence Summary Highlights" in ACL 2019, link: [https://aclanthology.org/D19-5408.pdf]
```bash
python3 task1_eval.py \
    -tf annotation/annotated_result/5_sample/aggregate_qlabels.jsonl \ # Attention highlighter do not need retrieval results
    -hl attn
    -mt summarization # or text-classification
    -m human-centered-summarization/financial-summarization-pegasus # or mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis
    -tk 5 # use top 5 highest attention score in target as label
    -d cuda:0
    -v | tee R.none_H.attn-sum.result
```
### Evaluate Retrieval methods with CnC Highlighter on task1
#### 1. Prepare the retrieval result
One shall first prepare the retrieval result of the annotation set in TREC format. 
```
target_id Q0 reference_id rank score tag
```
One can obtain a TREC format example of the retrieval method provided in ACL2023 paper "A Compare-and-contrast Multistage Pipeline for Uncovering Financial Signals in Financial Reports" (CnC-retrieval) by running the following command. 
```bash
python3 cnc_retrieve.py \
    -t annotation/annotated_result/5_sample/aggregate_qlabels.jsonl \
    -o result/5sample/cnc_retrieval.trec
```
#### 2. Evaluate the retrieval result with CnC Highlighter
For example, given the aggreagted 5-sample annotation set `annotation/annotated_result/5_sample/aggregate_qlabels.jsonl`, the compare-and-contrast (CnC) retrieval result for 5 samples is stored in `result/5sample/cnc_retrieval.trec`. Then the following command prints the evaluation result of highlighting given the compare-and-contrast highlighter. `-v` is used to print the detailed of each sample. For more options, please refer to the help message of by running `python3 task1_eval.py -h`. 
```bash
python3 task1_eval.py \ 
    -rf result/5sample/cnc_retrieval.trec \
    -tf annotation/annotated_result/5_sample/aggregate_qlabels.jsonl \
    -hl cnc \
    -lt 0.5 \
    -d cuda \
    -v | tee result/5sample/R.cnc_H.cnc.result
```
In order to keep naming consistency and make it easier to manage results, we recommend naming the retrieval result file (rf) as `result/{annotation_set_name}/{retrieval_method}_retrieval.trec` and the evaluation result file as `R.{retrieval_method}_H.{highlight_method}.result`. 
The result file contains the evaluation result of the retrieval method and the highlighter. 
For example, `cnc_retrieval.trec` contains the retrieval result of-CnC retrieval method and `R.cnc_H.cnc.result` contains the evaluation result of the CnC-retrieval method along with the CnC-highlighter.

User can also prepare the highlighting result in JSON format, and then evaluate the highlighting result with the following command:
```bash
python3 task1_eval.py \ 
    -tf result/5sample/cnc_highlighting.jsonl \
    -pf cnc-pred.json
    | tee result/5sample/R.cnc_H.cnc.result
```
The JSON file should be in the following format, take TARGET\_ID = "20221028\_10-K\_320193\_part2\_item7\_para1" as an example:
```json
{
    "20221028_10-K_320193_part2_item7_para1": {
        "id": TARGET_ID,
        "words_probs_tgt_mean": [0.1, 0.2, 0.3, 0.4, 0.5],
        "words_label_tgt_mean": [0, 0, 1, 1, 1],
        "highlight_spans_smooth": [
            "this is span 1",
            "this is span 2"
        ]
    }
    ...
}
```

#### 3. Evaluate the retrieval result with IR metrics
```bash
python3 task2_eval.py \ 
    -rf path/to/retrieval/result/in/TrecRun/format
    -tf path/to/annatated/label/in/TrecQrel/format
```

#### 4. Evaluate the retrieval result with LLM metrics
TBD.
