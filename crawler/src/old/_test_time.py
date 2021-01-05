import dateparser
import re

with open('../data/time.txt','r') as ftime:
    times = [time.strip().split('\t')[0] for time in ftime]
with open('../data/time.txt','w') as ftime:
    for time in times:
        ftime.write(time + '\t')
        
        # minor cleanup remove Z which is causing a lot of errors
        time = time.replace('Z', '')
        time = time.replace(': ', ' ')
        
        # fix 1
        fix_1 = re.findall(r'([\(\[]).*?([\)\]])', time)
        if len(fix_1) > 0:
            time = re.sub("([\(\[]).*?([\)\]])", "", time).strip().replace('  ',' ')
            time = time [:2] + ':' + time [2:]
            time_parsed = dateparser.parse(time, date_formats=['%H:%M %Z %B %d, %Y'])
        else:
            time_parsed = dateparser.parse(time)
        
        ftime.write(str(time_parsed) + '\n') 