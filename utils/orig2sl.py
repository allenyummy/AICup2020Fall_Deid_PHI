#encoding=utf-8
#author: Yu-Lun Chiang
#description: transform original data into sequence labeling data

import logging
import os

logger = logging.getLogger(__name__)


def loadInputFile(file_path):
    passage = list()   # store passage [content,content,...]
    position = list()  # store position [article_id, start_pos, end_pos, entity_text, entity_type, ...]
    mentions = dict()  # store mentions[mention] = Type
    
    with open(file_path, "r", encoding="utf8") as f:
        file_text = f.read().encode("utf-8").decode("utf-8-sig")
    data = file_text.split("\n\n--------------------\n\n")[:-1]
    for eachData in data:
        eachData = eachData.split("\n")
        content = eachData[0]
        passage.append(content)
        annotations=eachData[1:]
        for annot in annotations[1:]:
            annot=annot.split('\t') #annot= article_id, start_pos, end_pos, entity_text, entity_type
            position.extend(annot)
            mentions[annot[3]]=annot[4]
    return passage, position, mentions

def SLFormatData(passage, position, out_file_path):
    if (os.path.isfile(out_file_path)):
        os.remove(out_file_path)
    outputfile = open(out_file_path, 'a', encoding= 'utf-8')

    # output file lines
    count = 0 # annotation counts in each content
    tagged = list()
    for article_id in range(len(passage)):
        passage_split = list(passage[article_id])
        while '' or ' ' in passage_split:
            if '' in passage_split:
                passage_split.remove('')
            else:
                passage_split.remove(' ')
        start_tmp = 0
        for position_idx in range(0,len(position),5):
            if int(position[position_idx]) == article_id:
                count += 1
                if count == 1:
                    start_pos = int(position[position_idx+1])
                    end_pos = int(position[position_idx+2])
                    entity_type=position[position_idx+4]
                    if start_pos == 0:
                        token = list(passage[article_id][start_pos:end_pos])
                        whole_token = passage[article_id][start_pos:end_pos]
                        for token_idx in range(len(token)):
                            if len(token[token_idx].replace(' ','')) == 0:
                                continue
                            # BIO states
                            if token_idx == 0:
                                label = 'B-'+entity_type
                            else:
                                label = 'I-'+entity_type
                            
                            output_str = token[token_idx] + ' ' + label + '\n'
                            outputfile.write(output_str)

                    else:
                        token = list(passage[article_id][0:start_pos])
                        whole_token = passage[article_id][0:start_pos]
                        for token_idx in range(len(token)):
                            if len(token[token_idx].replace(' ','')) == 0:
                                continue
                            
                            output_str = token[token_idx] + ' ' + 'O' + '\n'
                            outputfile.write(output_str)

                        token = list(passage[article_id][start_pos:end_pos])
                        whole_token = passage[article_id][start_pos:end_pos]
                        for token_idx in range(len(token)):
                            if len(token[token_idx].replace(' ','')) == 0:
                                continue
                            # BIO states
                            if token[0] == '':
                                if token_idx == 1:
                                    label = 'B-'+entity_type
                                else:
                                    label = 'I-'+entity_type
                            else:
                                if token_idx == 0:
                                    label = 'B-'+entity_type
                                else:
                                    label = 'I-'+entity_type

                            output_str = token[token_idx] + ' ' + label + '\n'
                            outputfile.write(output_str)

                    start_tmp = end_pos
                else:
                    start_pos = int(position[position_idx+1])
                    end_pos = int(position[position_idx+2])
                    entity_type=position[position_idx+4]
                    if start_pos<start_tmp:
                        continue
                    else:
                        token = list(passage[article_id][start_tmp:start_pos])
                        whole_token = passage[article_id][start_tmp:start_pos]
                        for token_idx in range(len(token)):
                            if len(token[token_idx].replace(' ','')) == 0:
                                continue
                            output_str = token[token_idx] + ' ' + 'O' + '\n'
                            outputfile.write(output_str)

                    token = list(passage[article_id][start_pos:end_pos])
                    whole_token = passage[article_id][start_pos:end_pos]
                    for token_idx in range(len(token)):
                        if len(token[token_idx].replace(' ','')) == 0:
                            continue
                        # BIO states
                        if token[0] == '':
                            if token_idx == 1:
                                label = 'B-'+entity_type
                            else:
                                label = 'I-'+entity_type
                        else:
                            if token_idx == 0:
                                label = 'B-'+entity_type
                            else:
                                label = 'I-'+entity_type
                        
                        output_str = token[token_idx] + ' ' + label + '\n'
                        outputfile.write(output_str)
                    start_tmp = end_pos

        token = list(passage[article_id][start_tmp:])
        whole_token = passage[article_id][start_tmp:]
        for token_idx in range(len(token)):
            if len(token[token_idx].replace(' ','')) == 0:
                continue

            
            output_str = token[token_idx] + ' ' + 'O' + '\n'
            outputfile.write(output_str)

        count = 0
    
        output_str = '\n'
        outputfile.write(output_str)
        ID = passage[article_id]

        if article_id%10 == 0:
            print('Total complete articles:', article_id)

    # close output file
    outputfile.close()

if __name__ == "__main__":
    
    file = "data/orig/SampleData_deid.txt"
    out_file = "data/sl/SampleData_deid.txt"
    passage, position, mentions = loadInputFile(file)
    SLFormatData(passage, position, out_file)