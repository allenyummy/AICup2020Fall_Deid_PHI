# encoding=utf-8
# Author: Yu-Lun Chiang
# Description: bert-bilstm-crf model for sequence labeling

import logging
import torch
from torch.nn import Linear, LSTM, Dropout, CrossEntropyLoss
from transformers import BertConfig, BertPreTrainedModel, BertModel
from transformers.modeling_outputs import TokenClassifierOutput
from models.crf_layer import CRF

logger = logging.getLogger(__name__)


class BertBiLSTMCRFSLModel(BertPreTrainedModel):

    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.return_dict = config.return_dict if hasattr(config, "return_dict") else False
        self.bert = BertModel(config)
        self.dropout = Dropout(config.hidden_dropout_prob)
        self.lstm = LSTM(input_size=config.hidden_size, hidden_size=config.hidden_size, batch_first=True, bidirectional=True)
        self.classifier = Linear(config.hidden_size*2, config.num_labels)
        self.crf = CRF(num_tags=config.num_labels, batch_first=True)
        self.init_weights()
        
    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        labels=None,
        return_dict=None
    ):
        
        self.lstm.flatten_parameters()
        
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=self.return_dict
        )
        
        sequence_output = outputs[0]
        sequence_output = self.dropout(sequence_output)
        lstm_output = self.lstm(sequence_output)
        lstm_output = lstm_output[0]
        logits = self.classifier(lstm_output)
        
        loss = None
        if labels is not None:
            ## [TBD] change {label_id:-100 [CLS], [SEP], [PAD]} into {label_id:32 "O"}
            ## It means they contribute loss to loss function, so it need to be improved
            active_idx = labels != -100
            active_labels = torch.where(
                active_idx, labels, torch.tensor(0).type_as(labels)
            )
            loss = self.crf(emissions=logits, tags=active_labels, mask=attention_mask.type(torch.uint8))
            loss = -1*loss

        if self.return_dict:
            return TokenClassifierOutput(
                loss=loss,
                logits=logits,
                hidden_states=outputs.hidden_states,
                attentions=outputs.attentions,
            )
        else:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output
