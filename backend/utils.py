import os, os.path as osp 
import numpy as np
from time import time 

smpl_joint_names = [
    "hips", 
    "leftUpLeg", 
    "rightUpLeg", 
    "spine", 
    "leftLeg", 
    "rightLeg", 
    "spine1", 
    "leftFoot", 
    "rightFoot", 
    "spine2", 
    "leftToeBase", 
    "rightToeBase", 
    "neck", 
    "leftShoulder", 
    "rightShoulder", 
    "head", 
    "leftArm", 
    "rightArm", 
    "leftForeArm", 
    "rightForeArm", 
    "leftHand", 
    "rightHand", 
    "leftHandIndex1"
    "rightHandIndex1", 
]

def lazy_get_model_to_smpl(_index2joint): 
    """
    lazy mapper, which maps SMPL joints to character joints directly by their names
    """
    mappings = {}
    lower_smpl_joint_names = [name.lower() for name in smpl_joint_names]
    for index, joint_name in _index2joint.items(): 
        if joint_name.lower() not in lower_smpl_joint_names: 
            continue 
        smpl_index = lower_smpl_joint_names.index(joint_name.lower())
        mappings[index] = smpl_index 
    return mappings

def get_extra_uv_lines(infofile): 
    """
    parse lines that contain uv coords and detailed face information from *file generated by mayapy*
    *if you do no use model downloaded elsewhere, you do not need to use this function*
    """
    infile = infofile.replace(".txt", "_intermediate.obj")
    assert osp.exists(infile), "Can not find file {}, check whether you are using model downloaded from the internet. If so, run maya parser first".format(infile)
    lines = open(infile, "r").readlines()
    uv_lines = []
    for line in lines: 
        line = line.strip('\n').strip()
        if 'vt' in line or 'mtl' in line or 'f' in line or 'vn' in line: 
            uv_lines.append(line)
    return uv_lines

def clean_mtl(filename):
    lines = open(filename, "r").read().strip().split('\n')
    outlines = []
    for line in lines:
        if line.startswith('Kd'):
            vals = line.split(' ')[1:]
            rewrite = True
            for val in vals:
                if float(val) > 1e-8:
                    rewrite = False 
                    break
            if rewrite:
                line = "Kd 1.00 1.00 1.00"
                outlines.append(line)
            else:
                outlines.append(line)
        else:
            outlines.append(line)
    open(filename, "w").write('\n'.join(outlines))
    # print('\n'.join(outlines))

def clean_info(filename):
    """
    some fbx downloaded from the internet has strange pattern, clean that
    """
    with open(filename, "r") as f: 
        content = f.read().strip()
    start = content.find('mix')
    end = content.find(':')
    if start == -1 or end == -1: 
        return 
    pattern = content[start:end+1]
    # print(pattern)
    content = content.replace(pattern, "")
    with open(filename, "w") as f: 
        f.write(content)
    print('riginfo clean finished')

def parse_hier_from_riginfo_lines(lines):
    hier_lines = [line for line in lines if 'hier' in line]
    hier = {}; joint2index = {}; index = 0
    # parse rig info file and obtain kinematic chain(hierarchical structure)
    for line in lines: 
        line = line.strip('\n').strip()
        if line[:4] != 'hier': 
            continue
        splits = line.split(' ')
        parent_name = splits[1]
        child_name = splits[2]
        if parent_name not in joint2index: 
            joint2index[parent_name] = index 
            index += 1
        if child_name not in joint2index: 
            joint2index[child_name] = index 
            index += 1
        if parent_name not in hier:     hier[parent_name] = [child_name]
        else:   hier[parent_name].append(child_name)

    index2joint = {v: k for k, v in joint2index.items()}
    hier_index = {}
    for k, v in hier.items():   hier_index[joint2index[k]] = [joint2index[vv] for vv in v]
    parents = list(hier_index.keys())
    children = []
    for v in hier_index.values():   children.extend(v)
    root = [item for item in parents if item not in children]
    # assert len(root) == 1
    if len(root) != 1:
        print('unexpectedly find {} roots, return'.format(len(root)))
        return None, None
    root = root[0]

    # reorganize the index mapping to ensure that along each chain, 
    # from root node to leaf node, the index number increases
    new_hier = {}
    new_joint2index = {index2joint[root]: 0}
    top_level = [root]
    index = 1
    for item in top_level: 
        if item not in hier_index: 
            # print('continue')
            continue
        for child in hier_index[item]: 
            child_name = index2joint[child]
            if child_name not in new_joint2index: 
                new_joint2index[child_name] = index 
                index += 1
            if new_joint2index[index2joint[item]] not in new_hier: 
                new_hier[new_joint2index[index2joint[item]]] = []
            new_hier[new_joint2index[index2joint[item]]].append(new_joint2index[child_name])
            top_level.append(child)
    return new_hier, new_joint2index, hier_lines

def parse_skin_from_riginfo_lines(lines, joint2index):
    skin_lines = [line for line in lines if 'skin' in line]
    num_joints = len(list(joint2index.keys()))
    num_vertices = len(skin_lines)
    weights = np.zeros((num_joints, num_vertices), dtype=np.float32)
    for line in skin_lines: 
        line = line.strip().strip('\n')
        splits = line.split(" ")
        if len(splits) % 2 != 0: 
            print('strange skin line found, please use other 3D models')
            return None, None

        vertex_index = int(splits[1])
        for i in range(2, len(splits), 2): 
            joint_name = splits[i]
            weight = float(splits[i+1])
            weights[joint2index[joint_name]][vertex_index] = weight
    return weights, skin_lines

def parse_joints_from_riginfo_lines(lines, joint2index):
    num_joints = len(list(joint2index.keys()))
    # parse the T pose-skeleton
    joint_lines = [line for line in lines if 'joints' in line and line[:6] == 'joints']
    joints = np.zeros((num_joints, 3), dtype=np.float32)
    for joint_line in joint_lines: 
        joint_line = joint_line.strip().strip('\n')
        splits = joint_line.split(' ')
        name = splits[1]
        x = float(splits[2]); y = float(splits[3]); z = float(splits[4])
        joint_index = joint2index[name]
        joints[joint_index] = np.array([x, y, z])
    return joints, joint_lines

def timer(func):
    def func_wrapper(*args,**kwargs):
        time_start = time()
        result = func(*args,**kwargs)
        time_end = time()
        time_spend = time_end - time_start
        print('\n{0} cost time {1} s\n'.format(func.__name__, time_spend))
        return result
    return func_wrapper