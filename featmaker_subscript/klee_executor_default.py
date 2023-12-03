from multiprocessing import Process, Queue
import os
import time

configs = {
	'script_path': os.path.abspath(os.getcwd()),
    'b_dir': os.path.abspath('klee/build/'),
}

search_options = {
    "batching" : "--use-batching-search --batch-instructions=10000",
    "branching" : "--use-branching-search",
}

class klee_executor:
    def __init__(self, pconfig, max_core, top_dir, n_heuristics, base_time, options):
        self.pconfig = pconfig
        self.pgm = pconfig["pgm_name"]
        self.max_core = max_core
        self.top_dir = top_dir
        self.n_heuristics = n_heuristics
        self.base_time = base_time
        self.options = options
        self.execute_per_core = self.n_heuristics // self.max_core
        self.bin_dir = os.path.abspath('klee/build/bin')
    
    def gen_run_cmd(self, level, weight_idx , klee_max_time):
        argv = self.pconfig["sym_options"]
        
        search_key = "batching"
        if self.pgm in ["find", "sqlite3"]:
            search_key = "branching"

        search_stgy = "random-path --search=nurs:covnew"

        run_cmd = " ".join([self.bin_dir+"/klee", 
                                    "-only-output-states-covering-new", "--simplify-sym-indices", "--output-module=false",
                                    "--output-source=false", "--output-stats=false", "--disable-inlining", "--write-kqueries", 
                                    "--optimize", "--use-forked-solver", "--use-cex-cache", "--libc=uclibc", "--ignore-solver-failures",
                                    "--posix-runtime", "-env-file="+configs['b_dir']+"/../test.env",
                                    "--max-sym-array-size=4096", "--max-memory-inhibit=false",
                                    "--switch-type=internal", search_options[search_key], 
                                    "--watchdog -max-time="+str(klee_max_time), "--search="+search_stgy,
                                    self.pgm+".bc", argv, "1>/dev/null 2>/dev/null"])
        return run_cmd

    def run_klee(self, core_number, level, t_to_replay, klee_max_time, queue):
        start_time = time.time()
        core_dir = f"{self.top_dir}/Core{core_number}"
        os.chdir(core_dir+self.pconfig["exec_dir"])
        for t in range(t_to_replay):
            weight_idx = self.max_core * t + core_number
            run_cmd = self.gen_run_cmd(level, weight_idx, klee_max_time)
            with open(os.devnull, 'wb') as devnull:
                os.system(run_cmd)
            os.system(f"ls -l --time-style full-iso {core_dir+self.pconfig['exec_dir']}/klee-out-{t}/*.ktest > time_result")
            os.system(f"cp time_result klee-out-{t}")
            os.system(f"cp -r klee-out-{t} {self.top_dir}/result/{level}/{weight_idx}")
            os.system(f"rm -f time_result")
        os.system(f"rm -r klee-out-*")
        os.chdir(self.top_dir)
        queue.put(time.time()-start_time)

    def execute_klee(self, level, remaining_time):
        print("Execute KLEE in level: ", level)
        klee_max_time = min(self.base_time, remaining_time // self.n_heuristics)
        time_queue = Queue()
        procs= []
        for c in range(1, self.max_core + 1):
            t = self.execute_per_core 
            if c <= self.n_heuristics % self.max_core:
                t += 1
            procs.append(Process(target=self.run_klee, args=(c, level, t, klee_max_time, time_queue)))
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        executed_time = 0
        while not time_queue.empty():
            executed_time += time_queue.get()
        return executed_time