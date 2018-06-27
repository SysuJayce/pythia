import yaml
import argparse
import numpy as np
from torch.utils.data import DataLoader
from train_model.Engineer import one_stage_run_model, masked_unk_softmax
from train_model.dataset_utils import prepare_test_data_set
import torch
import json
import _pickle as pickle
import timeit
import sys
from train_model.model_factory import prepare_model


class answer_json:
    def __init__(self):
        self.answers = []

    def add(self, ques_id, ans):
        res = {
            "question_id": ques_id,
            "answer": ans
        }
        self.answers.append(res)


def build_model(config, dataset):
    assembler = dataset.assembler if hasattr(dataset, 'assembler') else None
    num_vocab_txt = dataset.vocab_dict.num_vocab
    num_vocab_nmn = 0 if assembler is None else len(assembler.module_names)
    num_choices = dataset.answer_dict.num_vocab

    num_image_feat = len(config['data']['image_feat_train'][0].split(','))
    myModel = prepare_model(num_vocab_txt, num_choices, **config['model'],
                            num_image_feat=num_image_feat)
    return myModel


def run_model(current_model, data_reader, UNK_idx=0):
    softmax_tot = []
    q_id_tot = []

    start = timeit.default_timer()
    for i, batch in enumerate(data_reader):
        if (i+1) % 100 == 0:
            end = timeit.default_timer()
            time = end - start
            start = timeit.default_timer()
            print(" process batch %d for test for %.1f s" % (i+1, time))
            sys.stdout.flush()

        verbose_info = batch['verbose_info']
        q_ids = verbose_info['question_id'].cpu().numpy().tolist()
        logit_res = one_stage_run_model(batch, current_model)
        softmax_res = masked_unk_softmax(logit_res, dim=1, mask_idx=UNK_idx)
        softmax_res = softmax_res.data.cpu().numpy().astype(np.float16)
        q_id_tot += q_ids
        softmax_tot.append(softmax_res)

    softmax_result = np.vstack(softmax_tot)

    return q_id_tot, softmax_result


def print_result(question_ids, soft_max_result, ans_dic, out_file, json_only=True,pkl_res_file=None):
    predicted_answers = np.argmax(soft_max_result, axis=1)

    if not json_only:
        with open(pkl_res_file, 'wb') as writeFile:
            pickle.dump(soft_max_result, writeFile)
            pickle.dump(question_ids, writeFile)
            pickle.dump(ans_dic, writeFile)

    ans_json_out = answer_json()
    for idx, pred_idx in enumerate(predicted_answers):
        question_id = question_ids[idx]
        pred_ans = ans_dic.idx2word(pred_idx)
        ans_json_out.add(question_id, pred_ans)

    ##dump the result
    with open(out_file, "w") as f:
        json.dump(ans_json_out.answers, f)