import sys
import argparse
from termcolor import colored
from pathlib import Path
from tqdm.auto import tqdm
from utils import read_jsonl, TYPE_MAP, TOPIC_MAP, SUBTOPIC_MAP
from aggregate import print_colored_highlight
def color_highlights(text, highlights, color='yellow'):
    for highlight in highlights:
        highlight = highlight.strip()
        text = text.replace(highlight, colored(highlight, color))
    return text


def classify_error(annotation):
    message = ''

    has_type = False
    for k, v in annotation["type"].items():
        if v != 0:
            has_type = True
            break
    
    is_trivial = None
    if has_type:
        if annotation["type"]["0"] == 1:
            is_trivial = True
        else:
            is_trivial = False


    has_topic = False
    for k, v in annotation["topic"].items():
        if v != 0:
            has_topic = True
            break

    has_highlight = annotation["highlight"] != ""

    if not has_topic:
        message += "[NO_TOPIC]"
    if not has_type:
        message += "[NO_TYPE]"

    if has_type:
        if is_trivial and has_highlight:
            message += "[TRIVIAL_BUT_HIGHLIGHT]"
        if not is_trivial and not has_highlight:
            message += "[NON_TRIVIAL_BUT_NO_HIGHLIGHT]"

    if message == '':
        message = colored("[NO_DEFINITION_ERROR]", "green")
    else:
        message = colored(message, "red")

    return message

if __name__ == "__main__":

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--input", '-i', help="Input file", required=True)
    argparser.add_argument("--restart_id", '-r', help="Restart from this ID")
    args = argparser.parse_args()
    annotations = read_jsonl(args.input)
    # bar = progressbar.ProgressBar(maxval=len(annotations), widgets=[progressbar.Bar('=', '[', ']'), ' ', progressbar.Percentage()])
    pbar = tqdm(total=len(annotations))
    
    # check if restart id exists
    found = False
    if args.restart_id: # command line argument have the highest priority
        restart_id = args.restart_id
    elif Path(".restart_id.tmp").exists():
        with open(".restart_id.tmp", "r") as f:
            restart_id = f.read().strip()
    else:
        restart_id = None

    start_index = 0
    if restart_id:
        for annotation in annotations:
            if annotation["id"] == restart_id:
                found = True
                break
            start_index += 1
        if not found:
            print("Restart ID not found")
            sys.exit(1)

    pbar.update(start_index)
    annotations = annotations[start_index:]
    print("=====================================")
    print("Start from lineno:", start_index + 1)
    print("=====================================")

    # view annotations
    for annotation in annotations:

        command = input('Press Enter to continue, q + Enter to quit: ')
        if command == 'q':
            with open(".restart_id.tmp", "w") as f:
                f.write(annotation["id"])
            break

 
        keys = annotation.keys()
        print(keys)
        if "naive_aggregation" in keys:
            tokens = annotation["tokens"]
            sample_id = annotation["sample_id"]
            print(f"Sample ID: {sample_id}")
            print('[probs]:', [round(v, 3) for v in annotation["highlight_probs"]])
            print_colored_highlight(annotation["highlight_probs"], tokens)
            print('[naive]:', annotation["naive_aggregation"]["label"])
            print_colored_highlight(annotation["naive_aggregation"]["label"], tokens)
            print('[loose]:', annotation["loose_aggregation"]["label"])
            print_colored_highlight(annotation["loose_aggregation"]["label"], tokens)
            print('[strict]:', annotation["strict_aggregation"]["label"])
            print_colored_highlight(annotation["strict_aggregation"]["label"], tokens)
            print('[harsh]:', annotation["harsh_aggregation"]["label"])
            print_colored_highlight(annotation["harsh_aggregation"]["label"], tokens)
            print('[complex]:', annotation["complex_aggregation"]["label"])
            print_colored_highlight(annotation["complex_aggregation"]["label"], tokens)
            print('='*50)

        else:
            message = classify_error(annotation)
            print("ID:", annotation["id"], ";lineno:", start_index + 1)
            print(message)
            num_of_types = sum(annotation["type"].values())
            if num_of_types != 1:
                num_of_types = colored(num_of_types, "red")
            print("Number of types:", num_of_types, "types dict:", annotation["type"])
            for k, v in annotation["type"].items():
                if v != 0:
                    print(colored(TYPE_MAP[k], "light_blue"))
            print("Highlight:")
            highlight = annotation["highlight"]
            if highlight == "":
                print("No highlight")
                # print("Text:")
                print(annotation["text"])
            else:
                # for h in highlight.split("|||"):
                #     print(h)
                # print("Text:")
                print("Number of highlights:", len(highlight.split("|||")))
                print(color_highlights(annotation["text"], highlight.split("|||"))) 
            print("Topics:", annotation["topic"])
            for k, v in annotation["topic"].items():
                if v != 0:
                    print(TOPIC_MAP[k])
            print("-" * 100)
            pbar.update(1)
            start_index += 1

"""
{"id": "20221028_10-K_320193_part2_item7_para1", "text": "the following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in part ii, item 8 of this form 10-k. this section of this form 10-k generally discusses 2022 and 2021 items and year-to-year comparisons between 2022 and 2021. discussions of 2020 items and year-to-year comparisons between 2021 and 2020 are not included in this form 10-k, and can be found in \"management's discussion and analysis of financial condition and results of operations\" in part ii, item 7 of the company's annual report on form 10-k for the fiscal year ended september 25, 2021.", "highlight": "", "type": {"0": 1, "1": 0, "2": 0, "3": 0, "4": 0}, "topic": {"1": 1, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "0": 0}}
"""
