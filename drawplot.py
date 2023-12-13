import matplotlib.pyplot as plt
import pickle
import os
from datetime import datetime

pgm = "find"
timebudget = 18000
result_dirs = ["FeatMaker", "KLEEDefault"]
labels = ["FeatMaker", "KLEE default"]

def date_handler(line):
    tokens = line.split()
    date = datetime.strptime(f"{tokens[5]} {tokens[6].split('.')[0]}", "%Y-%m-%d %H:%M:%S")
    ktest = tokens[-1].split('/')[-1]
    return date, ktest

def get_pc(ktest):
    kquery = ktest.split('.')[0] + '.kquery'
    if not os.path.exists(kquery):
        return []
    with open(kquery, 'r', errors='ignore') as f:
        lines = f.read().split('(query [\n')
    lines = lines[1].split('\n')[:-2]
    return lines

plt.figure(figsize=(6,4))
plt.ylabel('# of covered branches', fontdict={'size': 12})
plt.xlabel('time(h)', fontdict={'size': 12})
plt.xticks(range(0,timebudget + 1,3600),labels=range(timebudget//3600 + 1))
plt.grid(visible=True, linestyle="--", linewidth = "1")

for idx, result_dir in enumerate(result_dirs):
    result_base = f"featmaker_experiments/{result_dir}/{pgm}"
    data_files = os.popen(f"ls {result_base}/data/*.pkl").read().split()
    with open(f"{result_base}/data/{len(data_files)}.pkl", 'rb') as f:
        data = pickle.load(f)
    result = {}
    covered_set = set()
    start = None
    for level in range(0,100):
        if not os.path.exists(f"{result_base}/result/{level}"):
            break 
        for i in range(1, 50):
            if not os.path.exists(f"{result_base}/result/{level}/{i}"):
                break 
            with open(f"{result_base}/result/{level}/{i}/time_result", 'r') as f:
                lines = f.readlines()
            for l in lines:
                date, ktest = date_handler(l)
                pc = get_pc(f"{result_base}/result/{level}/{i}/{ktest}")
                pcidx = data['unique pc'].index(pc)
                for bsidx in range(len(data['unique branchset'])):
                    if pcidx in data['bsidx_clusters'][bsidx]:
                        covered_set |= data['unique branchset'][bsidx]
                        break
                if start == None:
                    start = date
                result[(date - start).seconds] = len(covered_set)

    x = sorted(result.keys())
    y = sorted([result[_] for _ in x])
    plt.plot(x,y, linewidth = "3.2", label=labels[idx])


plt.tight_layout()
plt.savefig("coverage.png")
