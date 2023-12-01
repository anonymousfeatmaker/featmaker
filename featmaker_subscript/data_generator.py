from multiprocessing import Process, Manager, Queue
import subprocess
import os
import time
import pickle

def branch_handler(ktest_gcov):
    with open(ktest_gcov, 'r', errors='ignore') as f:
        lines = f.read().split('        -:    0:Source')
    covered_branch = set()
    for s in lines:
        s = s.split('\n')
        src_name = s[0].split('/')[-1]
        check_branch = False
        line_idx = None
        for i, l in enumerate(s[1:]):
            if 'branch' in l and not check_branch:
                check_branch = True
                k = i
                while not ': ' in s[k]: k -= 1
                line_idx = s[k].split(':')[1].strip()
            if 'branch' in l:
                tmp = l.split()
                if tmp[2] == 'taken' and tmp[3] != '0%':
                    covered_branch.add(f"{src_name}_{line_idx}_{tmp[1]}")
            if not 'branch' in l and check_branch:
                check_branch = False
    os.system(f"rm {ktest_gcov}")
    return covered_branch

class data_generator:
    def __init__(self, pconfig, max_core, top_dir, n_weights, weight_func):
        self.pconfig = pconfig
        self.pgm = pconfig["pgm_name"]
        self.max_core = max_core
        self.top_dir = top_dir
        self.n_weights = n_weights
        self.n_to_replay = self.n_weights // self.max_core
        self.weight_func = weight_func
        self.bin_dir = os.path.abspath('klee/build/bin')
    
    def run_replay(self, core_number, level, t_to_replay, queue):
        start_time = time.time()
        gcov_dir = os.path.abspath(f"{self.pconfig['gcov_path']}{core_number}/{self.pconfig['exec_dir']}")
        gcda_file = self.pconfig["gcda_file"]
        gcov_file = self.pconfig["gcov_file"]
        for t in range(t_to_replay):
            trial = self.max_core * t + core_number
            ktest_lst = os.popen(f"ls {self.top_dir}/result/{level}/{trial}/*.ktest").read().split()
            os.chdir(gcov_dir)
            os.system(f"rm -f {gcda_file} {gcov_file}")
            covered_branches = {}
            for ktest in ktest_lst:
                process = subprocess.Popen(f"{self.bin_dir}/klee-replay ./{self.pgm} {ktest}", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                try:
                    _, stderr = process.communicate(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
                process.kill()
                    
                os.popen(f"gcov -b {gcda_file} 1>/dev/null 2>/dev/null; cat {gcov_file}>{ktest}_gcov 2>/dev/null; rm -f {gcda_file} {gcov_file} 2>/dev/null").read()
                covered_branches[ktest] = branch_handler(f"{ktest}_gcov")
                process.kill()
            os.chdir(self.top_dir)
            with open(f"{self.top_dir}/{trial}_result", 'wb') as f:
                pickle.dump(covered_branches, f)
        queue.put(time.time()-start_time)
    
    def generate_data(self, level):
        procs= []
        time_queue = Queue()
        for c in range(1, self.max_core + 1):
            t = self.n_to_replay 
            if c <= self.n_weights % self.max_core:
                t += 1
            procs.append(Process(target=self.run_replay, args=(c, level, t, time_queue)))
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        executed_time = 0
        while not time_queue.empty():
            executed_time += time_queue.get()
        return executed_time
