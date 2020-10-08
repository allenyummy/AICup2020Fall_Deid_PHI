output="article_id\tstart_position\tend_position\tentity_text\tentity_type\n"
pred_file = "outputs/test_predictions.txt"
out_tsv_file = "outputs/test_predictions.tsv"

def init():
    global pos
    global start_pos
    global end_pos
    global entity_text
    global entity_type
    start_pos = None
    end_pos = None
    entity_text = ""
    entity_type = None
    temp_type = None

init()
pos = 0
article_id = 0
with open(pred_file, "r", encoding="utf-8") as f:
    for line in f:
        if line == " \n":
            if start_pos is not None:
                end_pos = pos
                output_line = str(article_id) + "\t" + \
                            str(start_pos)  + "\t" + \
                            str(end_pos)    + "\t" + \
                            str(entity_text)+ "\t" + \
                            str(entity_type)+ "\n"
                output += output_line
            article_id += 1
            pos = 0
            init()
        
        else:
            split = line.rstrip().split()
            char, label = split[0], split[1]

            if label in ["O", "OO"]:
                if start_pos is not None:
                    end_pos = pos
                    output_line =   str(article_id) + "\t" + \
                                    str(start_pos)  + "\t" + \
                                    str(end_pos)    + "\t" + \
                                    str(entity_text)+ "\t" + \
                                    str(entity_type)+ "\n"
                    output += output_line
                    init()

            elif "B" in label:
                start_pos = pos
                entity_text += char
                entity_type = label[2:]
                temp_type = entity_type

            elif "I" in label:
                if temp_type is not None and temp_type == label[2:]:
                    entity_text += char
                elif temp_type or temp_type != label[2:]:
                    print ("I begins.... Fuck U ! ")
        pos += 1

with open(out_tsv_file,'w',encoding='utf-8') as f:
    f.write(output)