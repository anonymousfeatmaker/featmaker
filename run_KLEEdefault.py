from subprocess import Popen, PIPE
import json
import time
import os
import argparse

from featmaker_subscript import klee_executor_default
from featmaker_subscript import data_generator
from featmaker_subscript import feature_generator
from featmaker_subscript import weight_generator

exp_dir = "featmaker_experiments"

option_choices={
    "collect_func": ["pcidx", 'naive'],
    "cluster_func":["minset", "naive"],
    "weight_func":["random", "learn"],
    "abstract_level": range(0,4)
}

def load_pgm_config(config_file):
    with open(config_file, 'r') as f:
        parsed = json.load(f)
    return parsed

def kill_processes(pgm, top_dir):
    info_files = f"{top_dir}/*/*/*/info"
    info_lists = os.popen(f"ls {info_files}").read().split()
    for info in info_lists:
        with open(info, 'r') as f:
            lines = f.read().split('\n')
        if(len(lines) < 10):
            pid = lines[1].split()[1]
            os.system(f"kill -9 {pid}")


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    
    #Necessary options
    parser.add_argument("--pgm", required=True)
    parser.add_argument("--exp_base", required=True)
    
    parser.add_argument("--core", type=int, default=1)
    parser.add_argument("--time_budget", type=int, default=86400)
    parser.add_argument("--base_time", type=int, default=86400)
    parser.add_argument("--n_heuristics", type=int, default=1)
    
    #Task options
    parser.add_argument("--main_task", default="featmaker", choices=["featmaker", "naive"])
    
    #Branch-condition abstract options
    parser.add_argument("--abstract_level", type=int, default=1, choices=option_choices["abstract_level"])
    parser.add_argument("--lv_hp", type=int, default=8)
    parser.add_argument("--kvalue", type=int, default=3)


    args = parser.parse_args()
    
    heuristics_per_level = args.n_heuristics
    pgm = args.pgm
    max_core = args.core
    time_budget = args.time_budget
    base_time = args.base_time
    exp_base = args.exp_base
    
    extract_options = {
        "abstract_level" : args.abstract_level,
        "lv_hp" : args.lv_hp,
    }
    
    collect_func = "pcidx"
    cluster_func = "setcover"
    weight_func = "learn"
    
    if args.main_task == 'naive':
        collect_func = "naive"
        cluster_func = "naive"
        weight_func = "random"
        extract_options['abstract_level'] = 0
    
    kvalue = args.kvalue
    
    pconfig = load_pgm_config(f"pgm_config/{pgm}.json")
    top_dir = os.path.abspath(f"{exp_dir}/{exp_base}/{pgm}")
    root_dir = os.getcwd()
    data = {}
    if not os.path.exists(top_dir):
        os.makedirs(top_dir)
        os.mkdir(f"{top_dir}/result")
        os.mkdir(f"{top_dir}/features")
        os.mkdir(f"{top_dir}/data")
    else:
        print("Experiment directory with same name is already existing")
        exit()
    
    llvm_dir = os.path.abspath(pconfig["pgm_dir"])
    for c in range(1, max_core + 1):
        os.system(f"cp -r {llvm_dir} {top_dir}/Core{c}")

    ke = klee_executor_default.klee_executor(pconfig, max_core, top_dir, heuristics_per_level, base_time, extract_options)
    dg = data_generator.data_generator(pconfig, max_core, top_dir, heuristics_per_level, weight_func)
    fg = feature_generator.feature_generator(data, collect_func, cluster_func, extract_options, top_dir, heuristics_per_level)

    remaining_time = time_budget
    level = 0
    while remaining_time > 0:
        
        start_time = time.time()
        os.makedirs(f"{top_dir}/result/{level}")
        os.makedirs(f"{top_dir}/weight/{level}")

        if level != 0:
            fg.collect(level)
            
        remaining_time -= time.time() - start_time
        executed_time = ke.execute_klee(level, remaining_time)
        executed_time += dg.generate_data(level)
        
        remaining_time -= executed_time
        level += 1

    fg.collect(level)
    print(f"Ours finished!!")
    os.chdir(f"{top_dir}")
    
    os.system("rm -rf Core*")
    os.system("rm *_result")

    os.chdir(root_dir)
    kill_processes(pgm, top_dir)
            
