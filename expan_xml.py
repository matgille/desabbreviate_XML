import json
from collections import OrderedDict
from http.cookiejar import debug

from lxml import etree as ET
import sys
import os
import unicodedata
import re

from setuptools import glob

tei_namespace = 'http://www.tei-c.org/ns/1.0'
namespace_declaration = {'tei': tei_namespace}


def dictify(path):
    as_dict = OrderedDict()
    delimiter = "\t"
    with open(path, "r") as input_table:
        lines = [unicodedata.normalize('NFC', line) for line in input_table.readlines()]
        for idx, line in enumerate(lines):
            starts_and_stops = line.count("<SOT>") + line.count("<EOT>")
            replacements = line.count("~")
            if starts_and_stops != replacements:
                print(f"Error with line: {idx + 1}: {line}")
                exit(0)
            if starts_and_stops == 1:
                if "<SOT>" in line:
                    regexp = re.compile("[^\t]+\t~.+$")
                    match = re.match(regexp, line)
                    if not match:
                        print(f"Error with line: {idx + 1}: {line}. Please check the replacement")
                        exit(0)
                else:
                    regexp = re.compile("[^\t]+\t.+~$")
                    match = re.match(regexp, line)
                    if not match:
                        print(f"Error with line: {idx + 1}: {line}. Please check the replacement")
                        exit(0)
        lines = [line.replace("<SOT>", "([\.:; \n¬])") for line in lines]
        lines = [line.replace("<EOT>", "([\.:; \n¬])") for line in lines]
        lines = [line.replace("<ø>", "") for line in lines]
        lines = [re.sub(f"{delimiter}~", f"{delimiter}<FG>", line) for line in lines]
        lines = [re.sub("~$", "<EG>", line).replace("\n", "") for line in lines]
        lines = [line.replace("<FG>", "\\g<1>") for line in lines]
        lines = [line.replace("<EG>", "\\g<2>") if "\\g<1>" in line else line.replace("<EG>", "\\g<1>") for line in
                 lines]
        for idx, line in enumerate(lines):
            orig = line.split(delimiter)[0]
            try:
                reg = line.split(delimiter)[1]
            except IndexError:
                print(f"Error with line {idx}.")
                print(line.split(delimiter))
                exit(0)
            try:
                as_dict[orig] = (re.compile(orig), reg)
            except re.error as e:
                print(f"Error with line {idx}.")
                print(orig)
                print(e)
                exit(0)
    return as_dict


def main(input_file, expansion_table, expan_dict=None):
    replacements_list = []
    as_xml = ET.parse(input_file)
    all_lines = as_xml.xpath("//tei:lb", namespaces=namespace_declaration)
    all_breaks = as_xml.xpath("//tei:lb/@break", namespaces=namespace_declaration)
    print(input_file)
    all_pairs = []
    for index, line in enumerate(all_lines):
        line.tail = line.tail.replace("\n", " ")
        orig_line = line.tail
        orig_line = re.sub(r"\s{2,}", r" ", orig_line)
        # Gestion de l'hyphénation
        # TODO: réfléchir à comment donner du contexte sur le premier et dernier mot de la ligne
        try:
            if all_breaks[index + 1] == "no":
                line_text = line.tail + "~"
            else:
                line_text = line.tail + " "
        except IndexError:
            line_text = line.tail
        try:
            if all_breaks[index] == "no":
                line_text = "~" + line_text
            else:
                line_text = " " + line_text
        except IndexError:
            pass
        line.attrib.pop("corresp", None)
        current_facs = line.xpath("@facs")[0]
        try:
            orig_tail = unicodedata.normalize('NFC', line_text)
        except TypeError:
            print("Error")
            continue
        new_tail = unicodedata.normalize('NFC', line_text)
        for orig, (regexp, reg) in expansion_table.items():
            try:
                new_tail = re.sub(regexp, reg, new_tail)
            except re.error:
                print(f"Error in mapping. Please check: {orig}")
                exit(0)
        split_pattern = re.compile("[\.:; ]")
        expanded_sent_as_list = [item.replace("\n", "") for item in re.split(split_pattern, new_tail) if item != ""]
        orig_sent_as_list = [item.replace("\n", "") for item in re.split(split_pattern, orig_tail) if item != ""]
        if len(expanded_sent_as_list) != len(orig_sent_as_list):
            pass
        else:
            zipped = list(zip(orig_sent_as_list, expanded_sent_as_list))
            all_pairs.extend(zipped)
            for orig, reg in zipped:
                if orig != reg:
                    expan_dict[orig] = reg
        # Gestion de l'hyphénation
        try:
            if all_breaks[index + 1] == "no":
                new_tail = re.sub("~$", "", new_tail)
            else:
                new_tail = re.sub(" $", "", new_tail)
        except IndexError:
            pass
        try:
            if all_breaks[index] == "no":
                new_tail = re.sub("^~", "", new_tail)
            else:
                new_tail = re.sub("^ ", "", new_tail)
        except IndexError:
            pass
        new_tail = re.sub(r"\s{2,}", r" ", new_tail)
        line.tail = new_tail
        new_facs = f"{input_file.replace('.tokenized', '')}{current_facs}"
        # new_facs = f"{current_facs.replace('.tokenized', '')}"
        line.set("facs", new_facs)
        critical_chars = ["ᵛ","õ","̃","ꝙ","᷑","u̾","ͣ","ꝵ","","ͦ","ꝑ","̾","ͫ","᷒","ꝯ","ͨ","ͤ","ͬ","ͥ","ł","ꝟ","ẜ","ꝓ","ꝗ","Ꝗ","ͩ","⁊","ͧ","ᷤ","ͭ","ᷠ"]
        if any([char in new_tail for char in critical_chars]):
            replacements_list.append(f"{orig_line} --> {new_tail}")
    with open(input_file.replace(".xml", ".expanded.xml"), "w") as output_file:
        output_file.write(ET.tostring(as_xml, encoding='utf-8').decode('utf-8'))
    try:
        print('/'.join(input_file.split("/")[:-1]) + "/collatex/")
        os.mkdir('/'.join(input_file.split("/")[:-1]) + "/collatex/")
    except FileExistsError:
        pass
    with open('/'.join(input_file.split("/")[:-1]) + "/collatex/" + input_file.replace("_out.replaced.tokenized", "").split('/')[-1], "w") as output_file: 
        output_file.write(ET.tostring(as_xml, encoding='utf-8', pretty_print=True).decode('utf-8'))
    return expan_dict, all_pairs, replacements_list


if __name__ == '__main__':
    all_files = glob.glob(f"{sys.argv[1]}/sortie_HTR/*.tokenized.xml")
    print(sys.argv[1])
    print(all_files)
    print(f"{sys.argv[1]}/sortie_HTR/*.tokenized.xml")
    expansion_dict = {}
    expansion_table = dictify(sys.argv[2])
    all_couples = []
    replacement_list = []
    for file in all_files:
        expansion_dict, all_pairs, replacement = main(file, expansion_table, expan_dict=expansion_dict)
        all_couples.extend(all_pairs)
        replacement_list.extend(replacement)
    with open("logs/replacement_log.txt", "w") as output_file:
        output_file.write("\n".join(replacement_list))
    expansion_dict = sys.argv[3]
    with open(expansion_dict, "w") as output_dict:
        json.dump(expansion_dict, output_dict)
    all_couples = [item for item in all_couples if item[0] != item[1]]
    all_couples = list(set(all_couples))
    with open("logs/debug.tsv", "w") as output_debug:
        for orig, reg in all_couples:
            output_debug.write(f"{orig}\t{reg}\n")