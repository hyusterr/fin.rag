import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import transformers
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForMaskedLM, AutoModel, AutoConfig, Trainer, TrainingArguments, DataCollatorWithPadding
import evaluate
from datasets import load_dataset
from typing import List

FPB_label2id = {0: "negative", 1: "neutral", 2: "positive"}
FPB_id2label = {v: k for k, v in FPB_label2id.items()}

class BaseHighlighter:
    def __init__(self, model_name='bert-base-uncased', device='cuda'):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        self.method = None
        

    def highlight_outputs(
            self, 
            target, 
            text_reference,
            max_length=512,
            mean_aggregate=True,
            label_threshold=0.5,
            generate_spans=True
        ):
        raise NotImplementedError('highlight method not implemented')

    
    @staticmethod
    def mean_aggregate_highlights(highlight_results):
        # TODO: Add more aggregation methods, mean is the simplest
        word_probs_tgt = [highlight['word_probs_tgt'] for highlight in highlight_results]
        mean_word_probs_tgt = sum(word_probs_tgt) / len(word_probs_tgt)
        return mean_word_probs_tgt

    # TODO: combine topk and threshold labeling in abstraction

    @staticmethod
    def generate_highlight_spans(
            words_tgt: List[str], 
            word_label_tgt: List[int], 
            smoothen=True,
            max_gap=5,
        ):
        # ref: https://aclanthology.org/D19-5408.pdf
        # we actually will not know how many token need to be highlighted if we don't peek the true label
        # first version: use threshold labeling --> perform smoothing to generate spans
        # connecting two selected words if there is a small gap (<5 words) between them.
        # [0, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1] --> [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1]
        # span = ["token1 token2 token3 token4 token5", "token12"]
        # TODO: need to check edge cases

        smooth_tokenids = []
        start = None
        for i, label in enumerate(word_label_tgt):
            if label:
                smooth_tokenids.append(label)
                if start is None:
                    start = i
                if start is not None and i - start < max_gap:
                    smooth_tokenids[start:i+1] = [1] * (i - start + 1)
                start = i

            else:
                smooth_tokenids.append(label)
    
        i, spans = 0, []
        tmp = []
        for label in smooth_tokenids:
            if label:
                tmp.append(i)
            else:
                if tmp:
                    spans.append(tmp)
                    tmp = []
            i += 1
        highlight_spans_smooth = [' '.join(words_tgt[span[0]:span[-1]+1]) for span in spans]
 
        return smooth_tokenids, highlight_spans_smooth


class BERTHighlighter(BaseHighlighter):
    def __init__(self, model_name='bert-base-uncased', device='cuda'):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.highighter = AutoModelForTokenClassification.from_pretrained(model_name, num_labels=2)
        # need to check: if this class add softmax layer internally

    def forward(self, input_ids):
        outputs = self.highighter(input_ids, attention_mask)
        return outputs

    def highlight_outputs(
            self, 
            target, 
            text_reference=None,
            max_length=512,
            mean_aggregate=True,
            label_threshold=0.5,
            generate_spans=True
        ):
        # text_reference: not used in this highlighter
        
        input_ids = self.tokenizer.encode(target, return_tensors='pt', max_length=max_length, truncation=True)
        input_ids = input_ids.to(self.device)
        with torch.no_grad():
            outputs = self.forward(input_ids)
            logits = outputs.logits
            batch_probs = F.softmax(logits, dim=-1)
            batch_probs = batch_probs[:, :, 1].squeeze().cpu().numpy()


        outputs = []
        for i, probs in enumerate(batch_probs):
            # need to map the label of subword to the original word
            word_probs_tgt = probs
            word_label_tgt = (word_probs_tgt > label_threshold).astype(int)
            if generate_spans:
                smooth_tokenids, highlight_spans_smooth = self.generate_highlight_spans(
                    self.tokenizer.tokenize(target), 
                    word_label_tgt
                )
            else:
                highlight_spans_smooth = None

            outputs.append({
                'word_probs_tgt': word_probs_tgt,
                'word_label_tgt': word_label_tgt,
                'highlight_spans_smooth': highlight_spans_smooth
            })
