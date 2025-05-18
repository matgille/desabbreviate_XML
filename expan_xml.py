import json
from collections import OrderedDict

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
    with open(path, "r") as input_table:
        lines = [unicodedata.normalize('NFC', line) for line in input_table.readlines()]
        lines = [line.replace("<SOT>", "([\.:; \n¬])") for line in lines]
        lines = [line.replace("<EOT>", "([\.:; \n¬])") for line in lines]
        lines = [line.replace("<ø>", "") for line in lines]
        lines = [re.sub("\t~", "\t<FG>", line) for line in lines]
        lines = [re.sub("~$", "<EG>", line).replace("\n", "") for line in lines]
        lines = [line.replace("<FG>", "\\g<1>") for line in lines]
        lines = [line.replace("<EG>", "\\g<2>") if "\\g<1>" in line else line.replace("<EG>", "\\g<1>") for line in
                 lines]
        for idx, line in enumerate(lines):
            orig = line.split("\t")[0]
            try:
                reg = line.split("\t")[1]
            except IndexError:
                print(f"Error with line {idx}")
            as_dict[orig] = (re.compile(orig), reg)
    return as_dict


def main(input_file, expansion_table, lang=None, expan_dict=None):
    as_xml = ET.parse(input_file)
    if not lang:
        lang = as_xml.xpath("@xml:lang")[0]
    all_lines = as_xml.xpath("//tei:lb", namespaces=namespace_declaration)
    all_breaks = as_xml.xpath("//tei:lb/@break", namespaces=namespace_declaration)
    print(input_file)
    for index, line in enumerate(all_lines):
        line.tail = line.tail.replace("\n", " ")
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
        line.tail = new_tail
        new_facs = f"{input_file.replace('.tokenized', '')}{current_facs}"
        # new_facs = f"{current_facs.replace('.tokenized', '')}"
        line.set("facs", new_facs)

    with open(input_file.replace(".xml", ".expanded.xml"), "w") as output_file:
        output_file.write(ET.tostring(as_xml, encoding='utf-8').decode('utf-8'))
    try:
        os.mkdir('/'.join(input_file.split("/")[:-1]) + "/collatex/")
    except FileExistsError:
        pass
    with open('/'.join(input_file.split("/")[:-1]) + "/collatex/" + input_file.replace("_out.replaced.tokenized", "").split('/')[-1], "w") as output_file: 
        output_file.write(ET.tostring(as_xml, encoding='utf-8', pretty_print=True).decode('utf-8'))
    return expan_dict


if __name__ == '__main__':
    all_files = glob.glob(f"{sys.argv[1]}/*/*/sortie_HTR/*_out.tokenized.xml")
    expansion_dict = {}
    expansion_table = dictify(sys.argv[2])
    for file in all_files:
        expansion_dict = main(file, expansion_table, lang="la", expan_dict=expansion_dict)
    print(expansion_dict)
    expansion_dict = sys.argv[3]
    with open(expansion_dict, "w") as output_dict:
        json.dump(expansion_dict, output_dict)