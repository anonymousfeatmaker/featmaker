import os
import copy
import numpy as np
import pickle
import re

largeValRe = None

def abstract_condition(lines, lv_hp, abstract_level):
    if abstract_level == 0:
        return set(lines)
    result = set()
    largeValRe = re.compile("\\d{"+str(lv_hp)+",}")
    if abstract_level == 1:
        for line in lines:
            result.add(re.sub(largeValRe, "LargeValue", line))        
    elif abstract_level == 2:
        for line in lines:
            line = re.sub(largeValRe, "LargeValue", line)  
            result.add(re.sub("const_arr\\d+", "const_arr", line))
    elif abstract_level == 3:
        for line in lines:
            result.add(re.sub("const_arr\\d+", "const_arr", line))
    return result

def query_handler_naive(ktest_list):
    local_query_set = set()
    for ktest in ktest_list:
        kquery = ktest.split('.')[0] + '.kquery'
        with open(kquery, 'r', errors='ignore') as f:
            lines = f.read().split('(query [\n')
        lines = lines[1].split('\n')[:-2]
        local_query_set |= set(lines)
    return local_query_set

def get_pc(ktest):
    kquery = ktest.split('.')[0] + '.kquery'
    if not os.path.exists(kquery):
        return []
    with open(kquery, 'r', errors='ignore') as f:
        lines = f.read().split('(query [\n')
    lines = lines[1].split('\n')[:-2]
    return lines

def collect_naive(data, top_dir, level, n_heuristics):
    if level == 1:
        data["bsidx_clusters"] = {}
        data["unique branchset"] = []
        data["branches"] = set()
        data["plot data"] = []
    
    data["coverage"] = []

    for trial_number in range(1, n_heuristics+1):
        logfile = f"{top_dir}/{trial_number}_result"
        with open(logfile, 'rb') as f:
            tmp_covered_set = set()
            tmp_ktest_branch_dict = pickle.load(f)
            for ktest, bs in tmp_ktest_branch_dict.items():
                if bs not in data["unique branchset"]:
                    data["unique branchset"].append(bs)
                    # data["branches"] |= bs
                    data["bsidx_clusters"][len(data["unique branchset"]) - 1] = []
                bsidx = data["unique branchset"].index(bs)
                data["bsidx_clusters"][bsidx].append(ktest)
                tmp_covered_set |= bs
            data["coverage"].append(tmp_covered_set)
            data["branches"] |= tmp_covered_set
    data["plot data"].append(len(data["branches"]))
    with open(f"{top_dir}/data/{level}.pkl", 'wb') as f:
        pickle.dump(data, f)

def collect_pcidx(data, top_dir, level, n_heuristics):
    if level == 1:
        data["bsidx_clusters"] = {}
        data["unique branchset"] = []
        data["unique pc"] = []
        data["branches"] = set()
        data["plot data"] = []
        data["pre_covered"] = set()

    data["widx_info"] = np.zeros((n_heuristics,2))
    data["widx_pcidxes"] = {}
    tmp_covered_set = set()
    for trial_number in range(1, n_heuristics+1):
        trial_branches = set()
        data["widx_pcidxes"][trial_number - 1] = set()
        logfile = f"{top_dir}/{trial_number}_result"
        with open(logfile, 'rb') as f:
            tmp_ktest_branch_dict = pickle.load(f)
        for ktest, bs in tmp_ktest_branch_dict.items():
            tmp_pc = get_pc(ktest)

            if len(tmp_pc) == 0:
                continue
            
            if bs not in data["unique branchset"]:
                data["unique branchset"].append(bs)
                data["bsidx_clusters"][len(data["unique branchset"]) - 1] = set()
            
            if tmp_pc not in data["unique pc"]:
                data["unique pc"].append(tmp_pc)

            bsidx = data["unique branchset"].index(bs)
            
            pcidx = data["unique pc"].index(tmp_pc)
            data["widx_pcidxes"][trial_number - 1].add(pcidx)

            data["bsidx_clusters"][bsidx].add(pcidx)
            trial_branches |= bs

        if level != 1:
            data["widx_info"][trial_number - 1] = np.array([len(trial_branches - data["pre_covered"]), len(trial_branches)])
        tmp_covered_set |= trial_branches
    
    data["branches"] |= tmp_covered_set
    data["pre_covered"] = set()
    data["pre_covered"] |= tmp_covered_set
    data["plot data"].append(len(data["branches"]))
    with open(f"{top_dir}/data/{level}.pkl", 'wb') as f:
        pickle.dump(data, f)

collect_functions = {
    "naive" : collect_naive,
    "pcidx" : collect_pcidx,
}

def cluster_setcover(data):
    bs_br_matrix = np.full((len(data["unique branchset"]), len(data["branches"])), False)
    coverage_list = np.array([len(x) for x in data["unique branchset"]])
    br_dict = {}
    for br in data["branches"]:
        br_dict[br] = len(br_dict)
    for bsidx, bs in enumerate(data["unique branchset"]):
        for br in bs:
            bs_br_matrix[bsidx, br_dict[br]] = True
    local_bs = np.full(len(data["branches"]), False)
    
    tmp_minset = []
    while local_bs.sum() < len(data["branches"]):
        tmp_sum = bs_br_matrix.sum(axis=1)
        max_value = tmp_sum.max()
        tmp_bsidxes = np.where(tmp_sum == max_value)[0]
        new_bsidx = tmp_bsidxes[coverage_list[tmp_bsidxes].argmax()]
        tmp_minset.append(new_bsidx)
        local_bs += bs_br_matrix[new_bsidx]
        bs_br_matrix[:, np.where(local_bs)[0]] = False
    return tmp_minset

def cluster_naive(data):
    return list(data["bsidx_clusters"].keys())

calculate_functions = {
    "setcover": cluster_setcover,
    "naive" : cluster_naive,
}

class feature_generator:
    def __init__(self, data, collect_func, extract_func, extract_options, top_dir, n_heuristics):
        self.data = data
        self.n_heuristics = n_heuristics
        self.collect_function = collect_functions[collect_func]
        self.cluster_collection = calculate_functions[extract_func]
        self.extract_options = extract_options
        self.top_dir = top_dir
        self.read_opt = collect_func
        if collect_func == "pcidx":
            self.data["lv_hp"] = self.extract_options["lv_hp"]
            self.data["abstraction_level"] = self.extract_options["abstract_level"]

    def collect(self, level):
        self.collect_function(self.data, self.top_dir, level, self.n_heuristics)
        print(f"covered {self.data['plot data'][-1]} branches in iteration {level-1}")
    
    def extract_feature(self, level):
        self.data["cluster set"] = self.cluster_collection(self.data)
        self.data["features"] = set()
        if self.read_opt == "pcidx":
            for bsidx in self.data["cluster set"]:
                for pcidx in self.data["bsidx_clusters"][bsidx]:
                    self.data["features"] |= set(self.data["unique pc"][pcidx])
        else:
            for bsidx in self.data["cluster set"]:
                tmp_set = query_handler_naive(self.data["bsidx_clusters"][bsidx])
                self.data["features"] |= tmp_set

        self.data["features"] = abstract_condition(self.data["features"], self.extract_options["lv_hp"], self.extract_options["abstract_level"])
