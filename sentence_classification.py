# -*- coding: utf-8 -*-
"""sentence_classification.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1dwAsTRMMhoRGmFwLwcGHjtIPLhhFfFFU

1.   sentence 긍정, 부정 판독기 구현

2.   tokenizer: bert-base

3.   model: bert_for_sequence_classification
"""

!pip install transformers

!pip install wandb
import wandb

!wandb login

import os
import pdb
import argparse
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

import torch
from torch.nn.utils.rnn import pad_sequence
import torch.optim as optim

import numpy as np
from tqdm import tqdm, trange

from transformers import(
    BertForSequenceClassification,
    AutoTokenizer,
    AutoConfig,
    AdamW
)

def make_id_file(task, tokenizer):
  def make_data_strings(file_name):
    data_strings = []
    with open(os.path.join(file_name), 'r', encoding='utf-8') as f: # 파일 읽기
      id_file_data = [tokenizer.encode(line.lower()) for line in f.readlines()] # 소문자로 token encoding
    for item in id_file_data:
      data_strings.append(' '.join([str(k) for k in item])) # 각 토큰 encoding 띄어쓰기로 구분 (문자열 형태)
    return data_strings

  print('it will take some times...')
  train_pos = make_data_strings('sentiment.train.1') #긍정 train data
  train_neg = make_data_strings('sentiment.train.1') #부정 train data
  dev_pos = make_data_strings('sentiment.dev.1') #긍정 val data
  dev_neg = make_data_strings('sentiment.dev.1') #부정 val data

  print('make id file finished!')
  return train_pos, train_neg, dev_pos, dev_neg

from google.colab import files
uploaded = files.upload()

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased') #bert base tokenizer 생성(대소문자 구분x)

# 07.14. 18:03 first upload
# 07.14. 18:42 updated
# - dataset에 duplicated dataset이 대입되지 않는 문제 수정
# 07.15. 19:04 updated
# - Data augmentation 추가, train and val dataset duplication check, bug fixed

class ProjectDataLoader(object):
    def __init__(self, file_list, aug=None):
        self.file_list = file_list
        self.dataset = {}
        self.load()
        if aug:
            print(f'Wait for loading augmenter...')
            self.augmenter = self.load_augmenter()
        else:
            self.augmenter = None

    def load(self):
        print(f'Load datasets from {self.file_list}')
        for file_path in self.file_list:
            data_type, label = self.get_info_from_name(file_path)
            label = int(label)
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                self.dataset[file_path] = list(map(lambda x: x.strip(), lines))

    def get_info_from_name(self, name):
        data_type, label = name.split('.')[-2:]
        return data_type, label

    # Drop duplicated data.
    def drop_duplicated(self, verbose=False):
        print('-'*30)
        print('> Drop duplicated data')
        for name, dataset in self.dataset.items():
            print('-'*30)
            print(f'{name}')
            if 'dev' in name:
                train_set = set(self.dataset[name.replace('dev', 'train')])
                orig_len = len(dataset)
                val_set = set(dataset)
                val_set = val_set - train_set
                dataset = list(val_set)
                drop_len = len(dataset)
                self.dataset[name] = dataset
                print(f'drop duplicated with train: {orig_len:,} -> {drop_len:,}')

            orig_len = len(dataset)
            set_dataset = set(dataset)
            drop_len = len(set_dataset)
            num_duplicated = orig_len - drop_len
            
            print(f'duplicated : total / {num_duplicated:,} : {orig_len:,}')
            self.dataset[name] = list(set_dataset)
            print(f'{len(self.dataset[name]):,} sentences exist in {name}.')

    # Important part... We used this code before. But this method require dataset's name.
    def make_id_file(self, name, tokenizer):
        print(f'tokenizing {name}')
        data_strings = []
        id_file_data = [tokenizer.encode(line.lower()) for line in self.dataset[name]]
        for item in id_file_data:
            data_strings.append(' '.join([str(k) for k in item]))
        return data_strings

    def list_chunk(self, arr, n):
        return [arr[i: i + n] for i in range(0, len(arr), n)]

    def __getitem__(self, idx):
        return self.dataset[idx]

    # You don't need to look this method. This method shows information about our datasets.
    def summary(self):
        print('-'*30)
        print('> Summary')
        for name, dataset in self.dataset.items():
            data_type, label = self.get_info_from_name(name)
            num_of_sentences = len(dataset)
            print('-'*30)
            print(f'[{name}]')
            print(f'number of sentences: {num_of_sentences:,}')
            print(f'dataset type: {data_type}')
            print(f'label: {label}')

file_list = ['sentiment.train.0', 
             'sentiment.train.1', 
             'sentiment.dev.0', 
             'sentiment.dev.1']

datasets = ProjectDataLoader(file_list)
datasets.summary()
datasets.drop_duplicated()

train_pos = datasets.make_id_file('sentiment.train.1', tokenizer)
train_neg = datasets.make_id_file('sentiment.train.0', tokenizer)
val_pos = datasets.make_id_file('sentiment.dev.1', tokenizer)
val_neg = datasets.make_id_file('sentiment.dev.0', tokenizer)

#train_pos, train_neg, dev_pos, dev_neg = make_id_file('yelp', tokenizer)
# data 생성

#data와 label을 묶기 위한 class 생성 -> 모델에 같이 들어가야 함
class SentimentDataset(object):
  def __init__(self, tokenizer, pos, neg):
    self.tokenizer = tokenizer
    self.data = []
    self.label = []

    for pos_sent in pos:
      self.data += [self._cast_to_int(pos_sent.strip().split())] 
      self.label += [[1]] #긍정 label 1
    
    for neg_sent in neg:
      self.data += [self._cast_to_int(neg_sent.strip().split())] 
      self.label += [[0]] #부정 label 0


  def _cast_to_int(self, sample): #str인 token encoding을 int로 변환
    return [int(word_id) for word_id in sample]

  def __len__(self):
    return len(self.data)

  def __getitem__(self,index):
    sample = self.data[index]
    return np.array(sample), np.array(self.label[index])

#train, val dataset 생성 (data, label) 형태
train_dataset = SentimentDataset(tokenizer, train_pos, train_neg)
dev_dataset = SentimentDataset(tokenizer, val_pos, val_neg)

len(train_dataset)

#model의 매개변수인 input_ids, attention_mask, token_type_ids, position_ids, labels로 data 구성
def collate_fn_style(samples):
  input_ids, labels = zip(*samples)
  max_len = max(len(input_id) for input_id in input_ids) #input_ids 중 가장 긴 길이
  sorted_indices = np.argsort([len(input_id) for input_id in input_ids])[::-1] #input_ids len을 기준으로 내림차순한 index

  attention_mask = torch.tensor(
      [[1] * len(input_ids[index]) + [0] * (max_len - len(input_ids[index])) for index in sorted_indices]
  ) # attention mask는 해당 embedding token의 길이는 1로 채우고 나머지 길이(가장 긴 token - 현재 token 길이)는 0으로 채움
  input_ids = pad_sequence([torch.tensor(input_ids[index]) for index in sorted_indices], batch_first = True)
  #input_ids 는 가장 긴 input_id 부터 나열되는데 길이를 맞추기 위해 빈 부분은 0으로 padding, batch_first를 True로 하면
  #input_ids 의 shape은 batch_size * 가장 긴 input_id의 길이가 됨
  token_type_ids = torch.tensor([[0] * len(input_ids[index]) for index in sorted_indices])
  #문장 구분을 위함인데 batch 단위로 들어갈 땐 걍 다 0으로 채움
  position_ids = torch.tensor([list(range(len(input_ids[index]))) for index in sorted_indices])
  #토큰 별 고유 id
  labels = torch.tensor(np.stack(labels, axis=0)[sorted_indices])
  #내림차순 된 data의 label도 내림차순
  
  return input_ids, attention_mask, token_type_ids, position_ids, labels

train_batch_size=32
eval_batch_size=64

train_loader = torch.utils.data.DataLoader(train_dataset,
                                           batch_size=train_batch_size,
                                           shuffle=True, collate_fn=collate_fn_style,
                                           pin_memory=True, num_workers=2)
dev_loader = torch.utils.data.DataLoader(dev_dataset, batch_size=eval_batch_size,
                                         shuffle=False, collate_fn=collate_fn_style,
                                         num_workers=2)
#dataset을 iterable한 dataloader로 감싸기 -> train dataloader는 data를 섞어서 넣고 cuda에 올림.

#data loader 확인
next(iter(train_loader))

model = BertForSequenceClassification.from_pretrained('bert-base-uncased') #문장 분류를 위한 모델

random_seed = 42
np.random.seed(random_seed)
torch.manual_seed(random_seed)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = BertForSequenceClassification.from_pretrained('bert-base-uncased')
model.to(device) #gpu에 모델 올리기

def compute_acc(predictions, target_labels):
  return (np.array(predictions) == np.array(target_labels)).mean()
# label이 같으면 1, 다르면 0으로 평균을 냄 -> accuracy 계산용

#from transformers import get_linear_schedule_with_warmup

model.train()
learning_rate = 5e-5
train_epoch = 3
#total_training_steps = train_epoch * len(train_loader)
optimizer = AdamW(model.parameters(), lr=learning_rate)
scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda epoch: 0.65 ** epoch)

optimizer.param_groups[0]['lr']

wandb.init(project='Bert', config={'epoch' : 3, 'learning_rate' : 5e-5, 'learning_rate_scheduler': '0.65**epoch', 'delete_duplicate' : "yes"})
train_epoch = 3
lowest_valid_loss = 9999.
for epoch in range(train_epoch):
    with tqdm(train_loader, unit="batch") as tepoch:
        losses = [] #train loss 기록용
        for iteration, (input_ids, attention_mask, token_type_ids, position_ids, labels) in enumerate(tepoch):
            tepoch.set_description(f"Epoch {epoch}")
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            token_type_ids = token_type_ids.to(device)
            position_ids = position_ids.to(device)
            labels = labels.to(device, dtype=torch.long)

            optimizer.zero_grad()

            output = model(input_ids=input_ids,
                           attention_mask=attention_mask,
                           token_type_ids=token_type_ids,
                           position_ids=position_ids,
                           labels=labels)

            loss = output.loss
            losses.append(loss.item())
            loss.backward()
            optimizer.step()

            tepoch.set_postfix(loss=np.mean(losses)) # epoch의 1/20의 loss 출력
            if iteration != 0 and iteration % int(len(train_loader) / 20) == 0: # 한 epoch의 1/20마다 validation
                # Evaluate the model five times per epoch
                with torch.no_grad():
                    model.eval()
                    valid_losses = []
                    predictions = []
                    target_labels = []
                    for input_ids, attention_mask, token_type_ids, position_ids, labels in tqdm(dev_loader,
                                                                                                desc='Eval',
                                                                                                position=1,
                                                                                                leave=None):
                        input_ids = input_ids.to(device)
                        attention_mask = attention_mask.to(device)
                        token_type_ids = token_type_ids.to(device)
                        position_ids = position_ids.to(device)
                        labels = labels.to(device, dtype=torch.long)

                        output = model(input_ids=input_ids,
                                       attention_mask=attention_mask,
                                       token_type_ids=token_type_ids,
                                       position_ids=position_ids,
                                       labels=labels)

                        logits = output.logits
                        loss = output.loss
                        valid_losses.append(loss.item())

                        batch_predictions = [0 if example[0] > example[1] else 1 for example in logits]
                        batch_labels = [int(example) for example in labels]

                        predictions += batch_predictions
                        target_labels += batch_labels

                acc = compute_acc(predictions, target_labels)
                valid_loss = sum(valid_losses) / len(valid_losses)
                wandb.log({
                    'train_loss': np.mean(losses),
                    'val_loss': np.mean(valid_losses),
                    'acc': acc,
                    'learning_rate': optimizer.param_groups[0]['lr']
                })
                print(optimizer.param_groups[0]['lr'])
                print(f'acc: {acc}')
                losses = [] #train loss 갱신
                model.train()
                if lowest_valid_loss > valid_loss:
                    print('Acc for model which have lower valid loss: ', acc)
                    torch.save(model.state_dict(), "./pytorch_model.bin")
                    lowest_valid_loss = valid_loss
    scheduler.step()
wandb.finish()

import pandas as pd
test_df = pd.read_csv('test_no_label.csv')

test_dataset = test_df['Id']

def make_id_file_test(tokenizer, test_dataset):
    data_strings = []
    id_file_data = [tokenizer.encode(sent.lower()) for sent in test_dataset]
    for item in id_file_data:
        data_strings.append(' '.join([str(k) for k in item]))
    return data_strings

test = make_id_file_test(tokenizer, test_dataset)

class SentimentTestDataset(object):
    def __init__(self, tokenizer, test):
        self.tokenizer = tokenizer
        self.data = []

        for sent in test:
            self.data += [self._cast_to_int(sent.strip().split())]

    def _cast_to_int(self, sample):
        return [int(word_id) for word_id in sample]

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        sample = self.data[index]
        return np.array(sample)

test_dataset = SentimentTestDataset(tokenizer, test)

#test set에서 달라지는 점은 문장의 길이가 긴 순서대로 나열하지 않고 원래 순서대로 나열 
def collate_fn_style_test(samples):
    input_ids = samples
    max_len = max(len(input_id) for input_id in input_ids)
    #sorted_indices = np.argsort([len(input_id) for input_id in input_ids])[::-1]
    sorted_indices = range(len(input_ids))
    attention_mask = torch.tensor(
        [[1] * len(input_ids[index]) + [0] * (max_len - len(input_ids[index])) for index in
         sorted_indices])
    input_ids = pad_sequence([torch.tensor(input_ids[index]) for index in sorted_indices],
                             batch_first=True)
    token_type_ids = torch.tensor([[0] * len(input_ids[index]) for index in sorted_indices])
    position_ids = torch.tensor([list(range(len(input_ids[index]))) for index in sorted_indices])

    return input_ids, attention_mask, token_type_ids, position_ids

test_batch_size = 32
test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=test_batch_size,
                                          shuffle=False, collate_fn=collate_fn_style_test,
                                          num_workers=2)



with torch.no_grad():
    model.eval()
    predictions = []
    for input_ids, attention_mask, token_type_ids, position_ids in tqdm(test_loader,
                                                                        desc='Test',
                                                                        position=1,
                                                                        leave=None):

        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        token_type_ids = token_type_ids.to(device)
        position_ids = position_ids.to(device)

        output = model(input_ids=input_ids,
                       attention_mask=attention_mask,
                       token_type_ids=token_type_ids,
                       position_ids=position_ids)

        logits = output.logits
        batch_predictions = [0 if example[0] > example[1] else 1 for example in logits]
        predictions += batch_predictions

test_df['Category'] = predictions

test_df.to_csv('submission.csv', index=False)