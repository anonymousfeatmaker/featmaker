import random
import os
import numpy as np
import pickle
import re
from sklearn.cluster import KMeans

class random_weight_generator:
    def __init__(self, data, top_dir, n_weights, kvalue):
        self.data = data
        self.top_dir = top_dir
        self.n_weights = n_weights
        self.n_features = 26
        self.feature_idx = {}
    
    def random_weight(self):
        tmp_w = np.random.uniform(-10, 10, size=self.n_features)
        return [str(x) for x in tmp_w]
    
    def generate_weight(self, level):
        if level != 0:
            self.feature_idx = {}
            self.n_features = len(self.data["features"])
            with open(f"{self.top_dir}/features/{level}.f", 'w') as f:
                for feat in self.data["features"]:
                    f.write(feat+"\n")
                    self.feature_idx[len(self.feature_idx)] = feat
        for i in range(1,self.n_weights+1):
            with open(f"{self.top_dir}/weight/{level}/{i}.w", 'w') as f:
                for w in self.random_weight():
                    f.write(f"{w}\n")

class learning_weight_generator:
    def __init__(self, data, top_dir, n_weights, kvalue):
        self.data = data
        self.top_dir = top_dir
        self.n_weights = n_weights
        self.n_exploit = int(n_weights * 0.7)
        self.lv_hp = self.data["lv_hp"]
        self.abstract_level = self.data["abstraction_level"]
        self.feature_idx = {}
        self.classifier = KMeans(kvalue)

    def abstract_condition(self, lines):
        if self.abstract_level == 0:
            return set(lines)
        result = set()
        largeValRe = re.compile("\\d{"+str(self.lv_hp)+",}")
        if self.abstract_level == 1:
            for line in lines:
                result.add(re.sub(largeValRe, "LargeValue", line))        
        elif self.abstract_level == 2:
            for line in lines:
                line = re.sub(largeValRe, "LargeValue", line)  
                result.add(re.sub("const_arr\\d+", "const_arr", line))
        elif self.abstract_level == 3:
            for line in lines:
                result.add(re.sub("const_arr\\d+", "const_arr", line))
        return result

    def get_pc(self, ktest):
        kquery = ktest.split('.')[0] + '.kquery'
        with open(kquery, 'r', errors='ignore') as f:
            lines = f.read().split('(query [\n')
        lines = lines[1].split('\n')[:-2]
        return lines

    def get_scores(self):
        scores = (self.data["widx_info"])/(self.data["widx_info"].max(axis=0)+ 1)
        scores = scores.sum(axis=1)
        return scores
                    
    def write_feature_file(self, level):
        with open(f"{self.top_dir}/features/{level}.f", 'w') as f:
            feature_list = sorted(self.feature_idx.keys(), key=lambda x: self.feature_idx[x])
            for feature in feature_list:
                f.write(feature+"\n")

    def write_weight_file(self, level):
        for widx in range(1, self.n_weights+1):
            with open(f"{self.top_dir}/weight/{level}/{widx}.w", 'w') as f:
                for w in self.weights[:,widx-1]:
                    f.write(f"{w}\n")

    def gather_encountered_features(self, pcidxes):
        tmp_encountered = set()
        for pcidx in pcidxes:
            tmp_encountered |= self.abstract_condition(self.data["unique pc"][pcidx])
        return tmp_encountered
        
    def generate_weight(self, level):
        if level == 1:
            self.feature_idx = {}
            for feat in self.data["features"]:
                self.feature_idx[feat] = len(self.feature_idx)
            self.weights = np.random.uniform(-10, 10, (len(self.data["features"]), self.n_weights))
        else:
            remaining_features = list(set(self.feature_idx.keys()) & self.data["features"])
            remaining_distribution = {}
            
            if len(remaining_features) != 0:
                feature_encountered_score = np.zeros(self.n_weights)
                encountered_weights = np.zeros((len(remaining_features), self.n_weights))
                for widx in range(1, self.n_weights + 1):
                    encountered_features = self.gather_encountered_features(self.data["widx_pcidxes"][widx - 1])
                    feature_encountered_score[widx-1] = len(encountered_features)
                    for i, feat in enumerate(remaining_features):
                        if feat in encountered_features:
                            encountered_weights[i][widx - 1] = 1
                encountered_weights *= self.weights[np.array([self.feature_idx[x] for x in remaining_features])]
                self.feature_idx = {}
                for feat in self.data["features"]:
                    self.feature_idx[feat] = len(self.feature_idx)
                self.weights = np.random.uniform(-10, 10, (len(self.data["features"]), self.n_weights))
                scores = self.get_scores()
                self.classifier.fit(scores.reshape(-1,1))
                labels = self.classifier.labels_
                top_widx = np.zeros_like(scores)
                bot_widx = np.zeros_like(scores)
                top_widx[np.where(labels == labels[scores.argmax()])[0]] = 1
                bot_widx[np.where(labels == labels[scores.argmin()])[0]] = 1
                
                for i, pre_weights in enumerate(encountered_weights):
                    tmp_top = top_widx * pre_weights
                    tmp_bot = bot_widx * pre_weights
                    tmp_top = tmp_top[np.nonzero(tmp_top)[0]]
                    tmp_bot = tmp_bot[np.nonzero(tmp_bot)[0]]
                    
                    tm = np.nan
                    ts = np.nan
                    bm = np.nan
                    bs = np.nan
                    if tmp_top.size:
                        tm = tmp_top.mean()
                        ts = tmp_top.std()
                    if tmp_bot.size:
                        bm = tmp_bot.mean()
                        bs = tmp_bot.std()
                    
                    if np.isnan(tm) and np.isnan(bm):
                        continue
                    elif np.isnan(tm) and not np.isnan(bm):
                        self.weights[self.feature_idx[remaining_features[i]]] = -1 * np.abs(self.weights[self.feature_idx[remaining_features[i]], :self.n_weights])
                        remaining_distribution[remaining_features[i]] = (-10,-10)
                    elif not np.isnan(tm) and np.isnan(bm):
                        self.weights[self.feature_idx[remaining_features[i]]] = np.random.normal(tm, ts, self.n_weights)
                        remaining_distribution[remaining_features[i]] = (tm, ts)
                    elif np.abs(tm-bm) + np.abs(ts - bs) >= 1:
                        self.weights[self.feature_idx[remaining_features[i]]] = np.random.normal(tm, ts, self.n_weights)
                        remaining_distribution[remaining_features[i]] = (tm, ts)
                self.weights[self.weights > 10] = 10
                self.weights[self.weights < -10] = -10
                with open(f"{self.top_dir}/weight/{level}_dist.pkl", 'wb') as f:
                    pickle.dump(remaining_distribution, f)
            else:
                self.feature_idx = {}
                for feat in self.data["features"]:
                    self.feature_idx[feat] = len(self.feature_idx)
                self.weights = np.random.uniform(-10, 10, (len(self.data["features"]), self.n_weights))
            
        self.write_feature_file(level)
        self.write_weight_file(level)


weight_generators = {
    "random" : random_weight_generator,
    "learn" : learning_weight_generator,
}