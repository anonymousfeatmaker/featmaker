from subprocess import Popen, PIPE
import json
import time
import os
import optparse
import pickle

from featmaker_subscript import klee_executor
from featmaker_subscript import data_generator
from featmaker_subscript import feature_generator
from featmaker_subscript import weight_generator

def load_pgm_config(config_file):
    with open(config_file, 'r') as f:
        parsed = json.load(f)
    return parsed

if __name__=="__main__":
    parser = optparse.OptionParser()
    # Required Options
    parser.add_option(
        "--pgm",
        dest="pgm",
        help="Benchmarks : combine, csplit, diff, du, expr, find, gawk, gcal, grep, ls, make, patch, ptx, sqlite, trueprint",
        choices=["combine", "csplit", "diff", "du", "expr", "find", "gawk", "gcal", "grep", "ls", "make", "patch", "ptx", "sqlite", "trueprint"]
    )
    parser.add_option(
        "--output_dir",
        dest="output_dir",
        help="Result directory\n"
    )
    # Default Options
    parser.add_option(
        "--total_budget",
        dest="total_time",
        type="int",
        default=86400,
        help="Total time budget (sec) (Default: 86400 = 24h)\n"
    )
    parser.add_option(
        "--small_budget",
        dest="small_time",
        type="int",
        default=120,
        help="small time budget (sec) (Default: 120)\n"
    )
    parser.add_option(
        "--n_scores",
        dest="n_scores",
        type="int",
        default=20,
        help="The number of score functions in one iteration (Default: 20)\n"
    )
    # Featmaker or Naive
    parser.add_option(
        "--main_option",
        dest="main_option",
        default="featmaker",
        help="Main task to run : featmaker or naive (Default: featmaker)",
        choices=["featmaker", "naive"]
    )

    (options, args) = parser.parse_args()
    
    if options.pgm is None:
        print("Required option is empty: pgm")
        exit(1)
        
    if options.output_dir is None:
        print("Required option is empty: output_dir")
        exit(1)
            
    pgm = options.pgm
    output_dir = options.output_dir     
    exp_dir = f"{options.main_option}_experiments"
    top_dir = os.path.abspath(f"{exp_dir}/{output_dir}/{pgm}")
    root_dir = os.getcwd()
    data = {}
    if not os.path.exists(top_dir):
        os.makedirs(top_dir)
        os.mkdir(f"{top_dir}/result")
        os.mkdir(f"{top_dir}/weight")
        os.mkdir(f"{top_dir}/errors")
        os.mkdir(f"{top_dir}/features")
        os.mkdir(f"{top_dir}/data")
    else:
        print("Output directory is already existing")
        exit(1)
    
    pconfig = load_pgm_config(f"pgm_config/{pgm}.json")
    llvm_dir = os.path.abspath(pconfig["pgm_dir"])
    os.system(f"cp -r {llvm_dir} {top_dir}/")

    ke = klee_executor.klee_executor(pconfig, top_dir, options)
    dg = data_generator.data_generator(pconfig, top_dir, options)
    fg = feature_generator.feature_generator(data, top_dir, options)
    if options.main_option == "featmaker":
        wg = weight_generator.learning_weight_generator(data, top_dir, options.n_scores)
    else:
        wg = weight_generator.random_weight_generator(data, top_dir, options.n_scores)

    data = {}
    start_time = time.time()
    remaining_time = options.total_time
    iteration = 0
 
    while time.time() - start_time < options.total_time:    

        os.mkdir(f"{top_dir}/result/iteration-{iteration}")
        os.mkdir(f"{top_dir}/weight/iteration-{iteration}")

        if iteration != 0:
            print(f"Generate data in iteration: {iteration - 1}")
            dg.generate_data(iteration - 1)
            print(f"Generate features in iteration: {iteration - 1}")
            fg.collect(iteration)
            fg.extract_feature()
            print(f"Generate weights in iteration: {iteration - 1}")
            wg.generate_weight(iteration)
            
        remaining_time = options.total_time - (time.time() - start_time)
        ke.execute_klee(iteration, int(remaining_time))
        iteration += 1

    print(f"Testing Done. Please wait for collecting data")
    dg.generate_data(iteration - 1)
    fg.collect(iteration)
    print("Collecting Done")
    os.chdir(top_dir)
    error_inputs = []
    for i in range(iteration):
        if os.path.exists(f"{top_dir}/errors/{i}_potential_errors.pkl"):
            with open(f"{top_dir}/errors/{i}_potential_errors.pkl", 'rb') as f:
                error_inputs += pickle.load(f)
    with open(f"{top_dir}/error_inputs.txt", 'w') as f:
        f.write("\n".join(error_inputs))
    os.system("rm -rf obj-llvm")
    os.system("rm *_result.pkl")
    os.system("rm -r errors")

    os.chdir(root_dir)
            
