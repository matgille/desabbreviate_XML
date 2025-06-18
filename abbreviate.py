import json
from collections import OrderedDict
import random
from lxml import etree as ET
import sys
import os
import unicodedata
import re
import tqdm
# import pie
import multiprocessing as mp
from setuptools import glob


def clean_list(input_list):
    # On va nettoyer les listes
    for sent in input_list:
        to_remove = []
        for index, token in enumerate(sent):
            if token != "":
                pass
            elif token == "" and sent[index - 1] != ".":
                to_remove.append(index)
        [sent.pop(index) for index in reversed(to_remove)]
    return input_list


def dictify(path):
    """
    Produit un dictionnaire d'abbréviations à partir d'une table de désabreviations
    TODO: gérer la ponctuation.
    :param path:
    :return:
    """
    as_dict = dict()
    with open(path, "r") as input_table:
        lines = [unicodedata.normalize('NFC', line).replace("\n", "") for line in input_table.readlines()]
    lines = [re.sub("~", " ", line) for line in lines]
    lines = [line for line in lines if "<ø>" not in line]
    lines = [".\t\." if "." in line else line for line in lines]
    for line in lines:
        orig = line.split("\t")[0]
        reg = line.split("\t")[1]
        as_dict[orig] = re.sub("\s+", " ", reg)
    reversed_dict = dict()
    for orig, reg in as_dict.items():
        try:
            reversed_dict[reg].append(orig.replace("<EOT>", " ").replace("<SOT>", " "))
        except KeyError:
            reversed_dict[reg] = [orig.replace("<EOT>", " ").replace("<SOT>", " ")]

    with open("expansion_dict.json", "w") as output_dict:
        json.dump(expansion_dict, output_dict)

    with open("abbreviation_dict.json", "w") as output_dict:
        json.dump(reversed_dict, output_dict)

    return as_dict, reversed_dict


def abbreviate(line, reversed_dict):
    replacement_rate = 0.95 if random.random() < 0.3 else 0.45
    abbreviated_example = []
    orig_example = []
    line_to_append = line
    # On itère sur chaque expression, et on modifie peu à peu le token.
    replace = random.random()
    if replace > replacement_rate:
        abbreviated_example.append(line_to_append)
        orig_example.append(line)
        return orig_example, abbreviated_example
    for expression, replacements in reversed_dict.items():
        as_regexp = re.compile(expression)
        if re.search(as_regexp, line_to_append):
            if len(replacements) == 1:
                dice_roll = random.random()
                if dice_roll < replacement_rate:
                    replaced = re.sub(as_regexp, replacements[0], line_to_append)
                    line_to_append = replaced
            else:
                replace_or_not = random.random()
                if replace_or_not < replacement_rate:
                    dice_roll = random.randint(0, len(replacements) - 1)
                    replaced = re.sub(as_regexp, replacements[dice_roll], line_to_append)
                    line_to_append = replaced
    abbreviated_example.append(line_to_append)
    orig_example.append(line)
    return orig_example, abbreviated_example

def create_noise(abbr_line, orig_line):
    abbr_as_string = ""
    expansion_as_string = ""
    dice_roll = random.random()
    for idx, char in enumerate(abbr_line):
        if dice_roll < omission_rate:
            dice_roll = random.random()
            if dice_roll < .4:
                try:
                    abbr_line[idx] = confusion_dict[char]
                except KeyError:
                    continue
            abbr_as_string += " ".join([item for item in abbr_line if item]).strip() + "\n"
    abbr_as_string = re.sub("\n\s", "\n", abbr_as_string)
    zipped = list(zip(abbr_line, orig_line))
    for abbr, orig in zipped:
        if abbr is not None:
            expansion_as_string += f"{abbr}\t{orig}\n"
    return abbr_as_string, expansion_as_string

def main(input_file, expansion_table, expan_dict=None, confusion_dict=None, omission_rate=None):
    """
    Produit le corpus abrévié, à partir du dictionnaire.
    TODO: Une abréviation seulement par mot pour l'instant: voir si on peut aller + loin par de la récursivité
    :param input_file:
    :param expansion_table:
    :param expan_dict:
    :return:
    """
    expansion_table_as_dict, reversed_dict = dictify(expansion_table)
    with open(input_file, "r") as text_to_abbreviate:
        orig_text = text_to_abbreviate.read()
        text_as_list = [unicodedata.normalize('NFC', item) for item in orig_text.split("\n")]
    separators = re.compile(r"([.!,?;:\.])| ")
    splitted_text = [re.split(separators, line) for line in text_as_list]
    step = 5
    groupped = [splitted_text[step * n: step * n + step] for n in range(round(len(splitted_text) / step))]
    cleaned_list = []
    for group in groupped:
        interm_list = []
        for example in group:
            example = [token for token in example if token]
            example.append("\n")
            interm_list.extend(example)
        cleaned_list.append(" ".join(interm_list))
    new_text_as_list = []
    orig_list = []
    with mp.Pool(processes=16) as pool:
        # https://www.kite.com/python/answers/how-to-map-a-function-with-
        # multiple-arguments-to-a-multiprocessing-pool-in-python
        # Sort une liste des sorties sous la forme de liste de liste ici
        examples = pool.starmap(abbreviate, [(line, reversed_dict) for line in cleaned_list])

    # On rétablit les 2 listes
    for orig, abbr in examples:
        orig_list.append(orig)
        new_text_as_list.append(abbr)



    new_text_as_list = clean_list(new_text_as_list)
    orig_list = clean_list(orig_list)

    zipped = list(zip(new_text_as_list, orig_list))
    random.shuffle(zipped)
    with mp.Pool(processes=16) as pool:
        # https://www.kite.com/python/answers/how-to-map-a-function-with-
        # multiple-arguments-to-a-multiprocessing-pool-in-python
        # Sort une liste des sorties sous la forme de liste de liste ici
        noised = pool.starmap(create_noise, [(abbr_line, orig_line) for abbr_line, orig_line in zipped])
    abbr_as_string, expansion_as_string = "", ""
    for abbr, expan in noised:
        abbr_as_string += abbr
        expansion_as_string += expan
    with open(input_file.replace(".txt", ".abbreviated.txt"), "w") as output_file:
        output_file.write(abbr_as_string)
        # output_file.write(f"\n{orig_text}")

    with open("data/expansion_corpus.tsv", "w") as expansion_corpus:
        expansion_corpus.write(expansion_as_string)

    return expan_dict


if __name__ == '__main__':
    confusion_dict = {"t": "c",
                      "c": "t",
                      "n": "ii",
                      "t": "d",
                      "t": "r",
                      "c": "r",
                      "ro": "m",
                      "ꝑ": "ꝓ",
                      "ꝑ": "p",
                      "ꝗ": "q",
                      "ꝓ": "ꝑ",
                      "f": "s",
                      "ł": "l",
                      "̽": "ͬ",
                      "d": "cl",
                      "n": "ri",
                      "m": "ni"}
    omission_rate = .1

    my_file = sys.argv[1]
    expansion_table = sys.argv[2]
    expansion_dict = {}
    expansion_dict = main(my_file, expansion_table, expan_dict=expansion_dict, confusion_dict=confusion_dict, omission_rate=omission_rate)
    print(expansion_dict)
