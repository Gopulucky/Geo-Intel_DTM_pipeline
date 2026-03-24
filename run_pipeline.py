"""
Interactive Colab Launcher for the DTM, Hydrology, and Overlay pipelines.
"""

import os
import subprocess
import sys

VILLAGES = [
    "DEVDI_511671",
    "KHAPRETA_510206",
    "Dhal_Hoshiarpur_31235",
    "DHUNDA_FATEHGARH_SAHIB_32619",
    "67169_5NKR_CHAKHIRASINGH",
    "64334_2H_REFLIGHT",
    "PIRAYANKUPPAM",
    "THANDALAM",
    "Gandhinagar_Diglipur",
    "Kadamtala_Rangat",
]

def print_menu():
    print("\n" + "="*50)
    print("  HYDROLOGY PIPELINE LAUNCHER")
    print("="*50)
    print("Available Villages:")
    for i, v in enumerate(VILLAGES, 1):
        print(f"  {i:>2}. {v}")
    print("  11. ALL VILLAGES")
    print("="*50)

def ask_process():
    print("\nSelect Process to Run:")
    print("  1. DTM & Drainage Pipeline")
    print("  2. Hydrology Pipeline")
    print("  3. Overlay Visualization")
    print("  4. ALL PROCESSES")
    
    choice = input("Enter choice (1-4): ").strip()
    return choice

def run_process(script_name, village_name):
    print(f"\n" + "-"*50)
    print(f"---> Executing {script_name} for {village_name}...")
    print("-"*50)
    # Call the script using subprocess and pass the village name
    cmd = [sys.executable, script_name, village_name]
    subprocess.run(cmd)

def main():
    while True:
        print_menu()
        vill_choice = input("Select Village (1-11) or 'q' to quit: ").strip()
        
        if vill_choice.lower() == 'q':
            break
            
        try:
            vi = int(vill_choice)
            if 1 <= vi <= 10:
                selected_villages = [VILLAGES[vi-1]]
            elif vi == 11:
                selected_villages = VILLAGES
            else:
                print("Invalid choice. Try again.")
                continue
        except ValueError:
            print("Invalid input. Try again.")
            continue
            
        proc_choice = ask_process()
        if proc_choice not in ["1", "2", "3", "4"]:
            print("Invalid process choice. Try again.")
            continue
            
        scripts = []
        if proc_choice in ["1", "4"]:
            scripts.append("dtm_drainage_pipeline.py")
        if proc_choice in ["2", "4"]:
            scripts.append("colab_hydrology_pipeline.py")
        if proc_choice in ["3", "4"]:
            scripts.append("overlay_visualiser.py")
            
        for vill in selected_villages:
            for script in scripts:
                run_process(script, vill)

        print("\n" + "="*50)
        print("  PIPELINE EXECUTION COMPLETE")
        print("="*50 + "\n")

if __name__ == "__main__":
    main()
