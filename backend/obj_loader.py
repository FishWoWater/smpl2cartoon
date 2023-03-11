#!/usr/bin/env python
# coding=utf-8

import numpy as np 

#!/usr/bin/env python
# coding=utf-8

import numpy as np 

def _process_line(line):
    splits = line.split(' ')
    splits = [x.strip() for x in splits]
    splits = [x for x in splits if len(x) > 0]
    line = ' '.join(splits)

    if '//' not in line and '/' not in line:
        return line 
    items = line.split(' ')[1:]
    items = [item.strip() for item in items]
    if '//' in line:
        out_items = [item[:item.find('//')] for item in items]
    else:
        out_items = [item[:item.find('/')] for item in items]
    out = 'f ' + ' '.join(out_items)
    return out

class TriangleMesh:
    def __init__(self, filename): 
        self.vertices, self.triangles = self.load(filename)

    def load(self, filename):
        # print('reading from', filename)
        fp = open(filename, "r")
        lines = fp.read().strip().split('\n')
        vid = 0 
        fid = 0
        vertices = []
        triangles = []
        for line in lines: 
            if not line.startswith("v") and not line.startswith("f"):
                continue 
            if line.startswith("vt") or line.startswith("vn"):
                continue

            if line.startswith("v"):
                vertices.append(line.split(' ')[1:])
                vid += 1  
            else:
                line = _process_line(line)
                triangles.append(line.split(' ')[1:])
                fid += 1
        fp.close()
        vertices = np.array(vertices).reshape(-1, 3).astype(float)
        triangles = np.array(triangles).reshape(-1, 3).astype(int)
        return vertices, triangles

# class TriangleMesh:
#     def __init__(self, filename): 
#         self.vertices, self.triangles = self.load(filename)

#     def load(self, filename):
#         fp = open(filename, "r")
#         lines = fp.read().strip().split('\n')
#         vid = 0 
#         fid = 0
#         vertices = []
#         triangles = []
#         for line in lines: 
#             if not line.startswith("v") and not line.startswith("f"):
#                 continue 
#             if line.startswith("v"):
#                 vertices.append(line.split(' ')[1:])
#                 vid += 1  
#             else:
#                 triangles.append(line.split(' ')[1:])
#                 fid += 1
#         fp.close()
#         vertices = np.array(vertices).reshape(-1, 3).astype(np.float32)
#         triangles = np.array(triangles).reshape(-1, 3).astype(np.int)
#         return vertices, triangles
