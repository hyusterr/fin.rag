import numpy as np
import evaluate
from sklearn.metrics import roc_auc_score
from trectools import TrecQrel, TrecRun, TrecEval
# https://github.com/joaopalotti/trectools
from deepeval.metrics import ContextualRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval import evaluate as evaluate_deepeval
from utils.utils import retrieve_paragraph_from_docid
rouge = evaluate.load("rouge")

def get_r_precision(pred, truth):
    """
    Evaluate the R-Precision.
    - pred: list of predicted probability, e.g. [0.1, 0.9, 0.2, ...]
    - truth: list of truth, e.g. [0, 1, 0, ...]
    """
    r_truth = sum(truth)
    truth_index = [i for i, t in enumerate(truth) if t == 1]
    topr_pred_index = sorted(range(len(pred)), key=lambda i: pred[i], reverse=True)[:r_truth]
    r_precision = len(set(truth_index) & set(topr_pred_index)) / r_truth if r_truth > 0 else 0
    return r_precision

def get_precision_recall_f1(pred, truth):
    """
    Evaluate the precision, recall, and F1.
    - pred: list of predictions, e.g. [0, 1, 0, ...]
    - truth: list of truth, e.g. [0, 1, 0, ...]
    """
    tp = sum([1 for p, t in zip(pred, truth) if p == 1 and t == 1])
    fp = sum([1 for p, t in zip(pred, truth) if p == 1 and t == 0])
    fn = sum([1 for p, t in zip(pred, truth) if p == 0 and t == 1])
    tn = sum([1 for p, t in zip(pred, truth) if p == 0 and t == 0])
    precision = tp / (tp + fp) if tp + fp > 0 else 0
    recall = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
    return precision, recall, f1


def get_correlation(pred, truth):
    """
    Evaluate the correlation.
    - pred: list of predictions of probability, e.g. [0.1, 0.9, 0.2, ...]
    - truth: list of voting probability, e.g. [0.1, 0.9, 0.2, ...]
    """
    correlation = np.corrcoef(truth, pred)[0, 1]
    return correlation

def get_auc(pred, truth):
    """
    Evaluate the AUC.
    - pred: list of predictions of probability, e.g. [0.1, 0.9, 0.2, ...]
    - truth: list of truth, e.g. [0, 1, 0, ...]
    """
    auc = roc_auc_score(truth, pred)
    return auc

def get_f1(pred, truth):
    """
    Evaluate the F1.
    - pred: list of predictions, e.g. [0, 1, 0, ...]
    - truth: list of truth, e.g. [0, 1, 0, ...]
    """
    tp = sum([1 for p, t in zip(pred, truth) if p == 1 and t == 1])
    fp = sum([1 for p, t in zip(pred, truth) if p == 1 and t == 0])
    fn = sum([1 for p, t in zip(pred, truth) if p == 0 and t == 1])
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn > 0 else 0
    return f1


def evaluate_a_pair_highlight(pred, truth, agg_type='naive_aggregation'): #, pred_threshold=0.5) -> dict:
    """
    Evaluate a pair of predictions and truth.
    - pred: prediction after average of different ref-tgt pair dict, e.g. {
        "id": str, 
        "words_tgt": [str, ...],
        "words_probs_tgt_mean": [0, 0.66, ...],
        "words_label_tgt_mean": [0, 1, ...],
        "words_label_tgt_smooth": [0, 1, ...],
        "highlight_spans_smooth": [str, str, ..., ...],
    }
    - truth: dict, e.g. {
        "id": str, 
        "text": str, 
        "tokens": [str, ...],
        "highlight_probs": [0, 0.66, ...],
        "highlight_labels": [0, 1, ...],
        "highlight_spans": [[str, str, ...], ...],
        "type": str,
        "topic": str,
        "subtopic": str,
    }
    """
    # Check if the id matches
    assert pred["id"] == truth["id"], f"ID mismatch: {pred['id']} vs {truth['id']}"
    # Check if the length matches
    assert len(pred["words_probs_tgt_mean"]) == len(truth["highlight_probs"]), f"Length mismatch: {len(pred['pred_prob'])} vs {len(truth['highlight_probs'])}"

    # Convert the prediction to binary 
    # TODO: not sure if threshold is a parameter of evaluation or a parameter of prediction --> fixed to 0.5
    # pred_bin = [1 if p > pred_threshold else 0 for p in pred["pred_prob"]]
    pred_bin = pred["words_label_tgt_smooth"]
    pred_prob = pred["words_probs_tgt_mean"]

    try:
        truth_bin = truth["binary_labels"] # for expert set
        truth_prob = truth["binary_labels"] # we only have one expert, so the truth_prob is the same as truth_bin
    except:
        truth_bin = truth[agg_type]["highlight_labels"]
        truth_prob = truth["highlight_probs"]
    # Calculate the R-Precision
    r_precision = get_r_precision(pred_prob, truth_bin)


    # calculate the correlation 
    if np.std(truth_prob) != 0:
        correlation = get_correlation(pred_prob, truth_prob)
    else:
        correlation = np.nan

    # Calculate the metrics
    precision, recall, f1 = get_precision_recall_f1(pred_bin, truth_bin)

    if sum(truth_bin) == 0 or sum(truth_bin) == len(truth_bin):
        auc = np.nan # auc needs 2 classes
    else:
        auc = get_auc(pred_prob, truth_bin)

    # rouge seems non-sense for this task, skip it for now
    '''
    # calculate ROUGEs
    # pred_tokens = [truth["tokens"][i] for i, p in enumerate(pred_bin) if p == 1] 
    pred_tokens = pred["highlight_spans_smooth"]
    # TODO: do we need to consider splitting into spans considering the consecutive tokens? now is the simpliest version
    # TODO: the evaluate shall support some parallel processing, maybe not count at every single pair will be faster
    try:
        ref_tokens = " ".join(truth["highlight_spans"]) # it seems like this will be wrong when there are multiple spans
        # I have not yet prepare spans for the expert set

    except:
        ref_tokens = " ".join(truth[agg_type]["spans"]) # it seems like this will be wrong when there are multiple spans
    pred_tokens = " ".join(pred_tokens)
    # TODO: rouge implement batch inside, the efficiency has not yet been leveraged
    rouges = rouge.compute(predictions=[pred_tokens], references=[ref_tokens])
    '''
    
    
    # Return the metrics
    output = {
        "id": pred["id"],
        # "type": truth["type"],
        # "topic": truth["topic"],
        # "subtopic": truth["subtopic"],
        "r_precision": r_precision,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "correlation": correlation,
        "auc": auc,
    }
    # output.update(rouges)

    # print(output)

    return output
# TODO: the granularity of the evaluation is not clear, e.g. the evaluation of the whole dataset or the evaluation of each pair

def evaluate_spans_in_a_pair_highlight(pred, truth):
    # check if the id matches
    assert pred["id"] == truth["id"], f"ID mismatch: {pred['id']} vs {truth['id']}"

    # get the spans in truth
    tmp, spans_group_ids = [], []
    for i, t in enumerate(truth["highlight_labels"]):
        if t == 1:
            tmp.append(i)
        else:
            if tmp != []:
                spans_group_ids.append(tmp)
            tmp = []
    if tmp != []:
        spans_group_ids.append(tmp)

    # print("spans_group_ids", spans_group_ids)
    
    # TODO: if there is no span in the truth, the evaluation shall be 0
    if spans_group_ids == []:
        return {
            "id": pred["id"],
            "span_accuracy": np.nan,
            "span_exact_match": np.nan,
            # "span_auc": None,
        }

    spans_group_pred_probs, spans_group_truth_probs = [], []
    spans_group_pred_labels, spans_group_truth_labels = [], []
    for group in spans_group_ids:
        spans_group_pred_probs.append([pred["words_probs_tgt_mean"][i] for i in group])
        spans_group_pred_labels.append([pred["words_label_tgt_smooth"][i] for i in group])

        spans_group_truth_probs.append([truth["highlight_probs"][i] for i in group])
        spans_group_truth_labels.append([truth["highlight_labels"][i] for i in group])

    assert len(spans_group_pred_probs) == len(spans_group_truth_probs), "The number of spans in prediction and truth does not match"
    

    # evaluate the metrics by spans
    # accuracy
    accuracy = [sum(p) / sum(t) if sum(t) > 0 else 0 for p, t in zip(spans_group_pred_labels, spans_group_truth_labels)]
    accuracy = sum(accuracy) / len(accuracy)

    # exact match
    # e.g. id = [1, 2, 4, 5]
    # pred = [0.1, 0.9, 0.8, 0.8]
    # exact_match = 0.5
    each_exact_match = [1 if sum(p) == sum(t) else 0 for p, t in zip(spans_group_pred_labels, spans_group_truth_labels)]
    exact_match = sum(each_exact_match) / len(each_exact_match)
    
    # AUC
    # auc = [roc_auc_score(t, p) for p, t in zip(spans_group_pred_probs, spans_group_truth_labels)]
    # auc = sum(auc) / len(auc)

    # TODO: ROUGE (to extend the task to generation)

    # average the result of each span as the span-level evaluation
    # return the metrics

    
    output = {
        "id": pred["id"],
        "span_accuracy": accuracy,
        "span_exact_match": exact_match,
        # "span_auc": auc,
    }

    # print(output)
    
    return output


def evaluate_trec_qrels(preds, truths, K=10):
    """
    preds: filename of trec run format: target_id' 'Q0' 'doc_id' 'rank' 'score' 'run_id
    truths: filename trec qrels format: target_id' '0' 'doc_id' 'relevance'
    """
    run = TrecRun(preds)
    qrels = TrecQrel(truths)
    evaluator = TrecEval(run, qrels)
    # results = run.evaluate_run(qrels, per_query=True)
    ndcg = evaluator.get_ndcg(depth=K)
    recall = evaluator.get_recall(depth=K)
    precision = evaluator.get_precision(depth=K)
    results = {
        f"ndcg@{K}": ndcg,
        f"recall@{K}": recall,
        f"precision@{K}": precision,
    }
    return results


def evaluate_deepeval_context_relevancy(preds, llm, topK=10) -> dict:
    """
    preds: filename of trec run format: target_id' 'Q0' 'doc_id' 'rank' 'score' 'run_id
    llm: a class inherit deepeval.models.base_model.DeepEvalBaseLLM
    """
    # usage ref: https://github.com/joaopalotti/trectools/blob/418c970c3c37bc8f3b3a99d8178e8f9893bce1d5/trectools/trec_eval.py#L668
    run = TrecRun(preds).run_data
    topX_result = run.groupby("query")["docid"].apply(lambda x: x.head(topK).tolist()).to_dict()
    # already sort descending by score
    deepeval_testcases = [
            LLMTestCase(
                input=retrieve_paragraph_from_docid(target_id),
                actual_output=retrieve_paragraph_from_docid(target_id),
                retrieval_context=[retrieve_paragraph_from_docid(doc_id) for doc_id in context_ids]
                )
            for target_id, context_ids in topX_result.items()
            ]
    cr_metric = ContextualRelevancyMetric(model=llm)
    evaluate_deepeval(deepeval_testcases, [cr_metric])

