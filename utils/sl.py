# encoding=utf-8
# Author: Yu-Lun Chiang
# Description: utils of sequence labeling dataset

import logging
import os
from filelock import FileLock
from dataclasses import dataclass
from typing import List, Dict, Optional, TextIO
from transformers import PreTrainedTokenizer
import torch
from torch import nn
from torch.utils.data.dataset import Dataset

logger = logging.getLogger(__name__)


@dataclass
class InputExample:
    guid: str
    words: List[str]
    labels: Optional[List[str]]


@dataclass
class InputFeatures:
    input_ids: List[int]
    attention_mask: List[int]
    token_type_ids: Optional[List[int]] = None
    label_ids: Optional[List[int]] = None


class NerAsSLDataset(Dataset):
    
    features: List[InputFeatures]
    pad_token_label_id: int = nn.CrossEntropyLoss().ignore_index
    # Use cross entropy ignore_index as padding label id so that only
    # real label ids contribute to the loss later.

    def __init__(
        self,
        data_dir: str,
        filename: str,
        tokenizer: PreTrainedTokenizer,
        labels: List[str],
        model_type: str,
        max_seq_length: Optional[int]=None,
        doc_stride: Optional[int]=None,
        overwrite_cache=False
        ):
        self.set = filename.split(".")[0]

        # Load data features from cache or dataset file
        cached_features_file = os.path.join(
            data_dir, "cached_{}_{}_{}".format(self.set, tokenizer.__class__.__name__, str(max_seq_length)))

        # Make sure only the first process in distributed training processes the dataset,
        # and the others will use the cache.
        lock_path = cached_features_file + ".lock"
        with FileLock(lock_path):
            if os.path.exists(cached_features_file) and not overwrite_cache:
                logger.info(f"Loading features from cached file {cached_features_file}")
                self.features = torch.load(cached_features_file)
            else:
                file_path = os.path.join(data_dir, filename)
                logger.info(f"Creating features from dataset file at {file_path}")
                examples = read_examples_from_file(file_path)
                # TODO clean up all this to leverage built-in features of tokenizers
                self.features = convert_examples_to_features(
                    examples,
                    labels,
                    max_seq_length,
                    doc_stride,
                    tokenizer,
                    cls_token_at_end=bool(model_type in ["xlnet"]),  # xlnet has a cls token at the end
                    cls_token=tokenizer.cls_token,
                    cls_token_segment_id=2 if model_type in ["xlnet"] else 0,
                    sep_token=tokenizer.sep_token,
                    sep_token_extra=False,  # roberta uses an extra separator b/w pairs of sentences, cf. github.com/pytorch/fairseq/commit/1684e166e3da03f5b600dbb7855cb98ddfcd0805
                    pad_on_left=bool(tokenizer.padding_side == "left"),
                    pad_token=tokenizer.pad_token_id,
                    pad_token_segment_id=tokenizer.pad_token_type_id,
                    pad_token_label_id=self.pad_token_label_id,
                )
                logger.info(f"Saving features into cached file {cached_features_file}")
                torch.save(self.features, cached_features_file)
    
    def __len__(self):
        return len(self.features)

    def __getitem__(self, i) -> InputFeatures:
        return self.features[i]

def read_examples_from_file(file_path: str) -> List[InputExample]:
    guid_index = 1
    examples = []
    with open(file_path, "r", encoding="utf-8") as f:
        words = []
        labels = []
        for line in f:
            line = line.rstrip()
            if line.startswith("-DOCSTART-") or line == "" or line == "\n":
                if words:
                    examples.append(InputExample(guid=f"{file_path}-{guid_index}", words=words, labels=labels))
                    guid_index += 1
                    words = []
                    labels = []
            else:
                splits = line.split(" ")
                words.append(splits[0])
                labels.append(splits[1] if len(splits) > 1 else "O")
        if words:
            examples.append(InputExample(guid=f"{file_path}-{guid_index}", words=words, labels=labels))
    return examples

def convert_examples_to_features(
    examples: List[InputExample],
    labels: List[str],
    max_seq_length: int,
    doc_stride: int,
    tokenizer: PreTrainedTokenizer,
    cls_token_at_end=False,
    cls_token="[CLS]",
    cls_token_segment_id=1,
    sep_token="[SEP]",
    sep_token_extra=False,
    pad_on_left=False,
    pad_token=0,
    pad_token_segment_id=0,
    pad_token_label_id=-100,
    sequence_a_segment_id=0,
    mask_padding_with_zero=True,
) -> List[InputFeatures]:
    """ Loads a data file into a list of `InputFeatures`
        `cls_token_at_end` define the location of the CLS token:
            - False (Default, BERT/XLM pattern): [CLS] + A + [SEP] + B + [SEP]
            - True (XLNet/GPT pattern): A + [SEP] + B + [SEP] + [CLS]
        `cls_token_segment_id` define the segment id associated to the CLS token (0 for BERT, 2 for XLNet)
    """
    # TODO clean up all this to leverage built-in features of tokenizers

    label_map = {label: i for i, label in enumerate(labels)}

    features = []
    for (ex_index, example) in enumerate(examples):
        if ex_index % 10_000 == 0:
            logger.info("Writing example %d of %d", ex_index, len(examples))
        
        tokens = []
        label_ids = []
        for word, label in zip(example.words, example.labels):
            word_tokens = tokenizer.tokenize(word)

            # bert-base-multilingual-cased sometimes output "nothing ([]) when calling tokenize with just a space.
            if len(word_tokens) > 0:
                tokens.extend(word_tokens)
                # Use the real label id for the first token of the word, and padding ids for the remaining tokens
                label_ids.extend([label_map[label]] + [pad_token_label_id] * (len(word_tokens) - 1))

        
        i = 0
        special_tokens_count = tokenizer.num_special_tokens_to_add()
        max_real_tokens_length = max_seq_length - special_tokens_count
        while len(tokens) > max_real_tokens_length*(i+1):
            child_tokens = tokens[max_real_tokens_length*i: max_real_tokens_length*(i+1)]
            child_label_ids = label_ids[max_real_tokens_length*i: max_real_tokens_length*(i+1)]
            i += 1
            
            child_tokens += [sep_token]
            child_label_ids += [pad_token_label_id]
            if sep_token_extra:
                # roberta uses an extra separator b/w pairs of sentences
                child_tokens += [sep_token]
                child_label_ids += [pad_token_label_id]
            segment_ids = [sequence_a_segment_id] * len(child_tokens)

            if cls_token_at_end:
                child_tokens += [cls_token]
                child_label_ids += [pad_token_label_id]
                segment_ids += [cls_token_segment_id]
            else:
                child_tokens = [cls_token] + child_tokens
                child_label_ids = [pad_token_label_id] + child_label_ids
                segment_ids = [cls_token_segment_id] + segment_ids

            input_ids = tokenizer.convert_tokens_to_ids(child_tokens)

            # The mask has 1 for real tokens and 0 for padding tokens. Only real
            # tokens are attended to.
            input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

            # Zero-pad up to the sequence length.
            padding_length = max_seq_length - len(input_ids)
            if pad_on_left:
                input_ids = ([pad_token] * padding_length) + input_ids
                input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
                segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
                child_label_ids = ([pad_token_label_id] * padding_length) + child_label_ids
            else:
                input_ids += [pad_token] * padding_length
                input_mask += [0 if mask_padding_with_zero else 1] * padding_length
                segment_ids += [pad_token_segment_id] * padding_length
                child_label_ids += [pad_token_label_id] * padding_length

            assert len(input_ids) == max_seq_length
            assert len(input_mask) == max_seq_length
            assert len(segment_ids) == max_seq_length
            assert len(child_label_ids) == max_seq_length

            if ex_index < 5:
                logger.info("*** Example ***")
                logger.info("guid: %s", example.guid)
                logger.info("tokens: %s", " ".join([str(x) for x in child_tokens]))
                logger.info("input_ids: %s", " ".join([str(x) for x in input_ids]))
                logger.info("input_mask: %s", " ".join([str(x) for x in input_mask]))
                logger.info("segment_ids: %s", " ".join([str(x) for x in segment_ids]))
                logger.info("label_ids: %s", " ".join([str(x) for x in child_label_ids]))
            
            if "token_type_ids" not in tokenizer.model_input_names:
                segment_ids = None

            features.append(
                InputFeatures(
                    input_ids=input_ids, attention_mask=input_mask, token_type_ids=segment_ids, label_ids=child_label_ids
                )
            )
        else:
            child_tokens = tokens[max_real_tokens_length*i:]
            child_label_ids = label_ids[max_real_tokens_length*i:]
        
            child_tokens += [sep_token]
            child_label_ids += [pad_token_label_id]
            if sep_token_extra:
                # roberta uses an extra separator b/w pairs of sentences
                child_tokens += [sep_token]
                child_label_ids += [pad_token_label_id]
            segment_ids = [sequence_a_segment_id] * len(child_tokens)

            if cls_token_at_end:
                child_tokens += [cls_token]
                child_label_ids += [pad_token_label_id]
                segment_ids += [cls_token_segment_id]
            else:
                child_tokens = [cls_token] + child_tokens
                child_label_ids = [pad_token_label_id] + child_label_ids
                segment_ids = [cls_token_segment_id] + segment_ids

            input_ids = tokenizer.convert_tokens_to_ids(child_tokens)

            # The mask has 1 for real tokens and 0 for padding tokens. Only real
            # tokens are attended to.
            input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

            # Zero-pad up to the sequence length.
            padding_length = max_seq_length - len(input_ids)
            if pad_on_left:
                input_ids = ([pad_token] * padding_length) + input_ids
                input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
                segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
                child_label_ids = ([pad_token_label_id] * padding_length) + child_label_ids
            else:
                input_ids += [pad_token] * padding_length
                input_mask += [0 if mask_padding_with_zero else 1] * padding_length
                segment_ids += [pad_token_segment_id] * padding_length
                child_label_ids += [pad_token_label_id] * padding_length

            assert len(input_ids) == max_seq_length
            assert len(input_mask) == max_seq_length
            assert len(segment_ids) == max_seq_length
            assert len(child_label_ids) == max_seq_length

            if ex_index < 5:
                logger.info("*** Example ***")
                logger.info("guid: %s", example.guid)
                logger.info("tokens: %s", " ".join([str(x) for x in child_tokens]))
                logger.info("input_ids: %s", " ".join([str(x) for x in input_ids]))
                logger.info("input_mask: %s", " ".join([str(x) for x in input_mask]))
                logger.info("segment_ids: %s", " ".join([str(x) for x in segment_ids]))
                logger.info("label_ids: %s", " ".join([str(x) for x in child_label_ids]))

            if "token_type_ids" not in tokenizer.model_input_names:
                segment_ids = None

            features.append(
                InputFeatures(
                    input_ids=input_ids, attention_mask=input_mask, token_type_ids=segment_ids, label_ids=child_label_ids
                )
            )
    return features

def write_predictions_to_file(writer: TextIO, test_input_reader: TextIO, preds_list: List):
    example_id = 0
    for line in test_input_reader:
        if line.startswith("-DOCSTART-") or line == "" or line == "\n" or line == " \n":
            writer.write(line)
            if not preds_list[example_id]:
                example_id += 1
        elif preds_list[example_id]:
            output_line = line.rstrip() + " " + preds_list[example_id].pop(0) + "\n"
            writer.write(output_line)
        else:
            output_line = line.rstrip() + " " + "No prediciton due to limitation of max-seq-length" + "\n"
            writer.write(output_line)
            logger.warning("Maximum sequence length exceeded: No prediction for '%s'.", line.rstrip())

def get_labels(path: str) -> List[str]:
    with open(path, "r") as f:
        labels = f.read().splitlines()
    if "O" not in labels:
        labels = ["O"] + labels
    return labels
