import sys
import maya 
import maya.standalone 
maya.standalone.initialize(name='python')

import maya.OpenMaya as om
import maya.cmds as cmds
import pymel.core as pm
import maya.mel as mel
import numpy as np
import os
import glob

def _getHierarchyRootJoint(joint=""):
    """
    Function to find the top parent joint node from the given 
    'joint' maya node
    Args:
        joint (string) : name of the maya joint to traverse from
    Returns:
        A string name of the top parent joint traversed from 'joint'
    Example:
        topParentJoint = _getHierarchyRootJoint( joint="LShoulder" )
    """
    # Search through the rootJoint's top most joint parent node
    rootJoint = joint
    while (True):
        parent = cmds.listRelatives(rootJoint, parent=True, type='joint')
        if not parent:
            break
        rootJoint = parent[0]
    return rootJoint

def getGeometryGroups():
    geo_list = []
    geometries = cmds.ls(type='surfaceShape')
    for geo in geometries:
        if 'ShapeOrig' in geo:
            '''
            we can also use cmds.ls(geo, l=True)[0].split("|")[0]
            to get the upper level node name, but stick on this way for now
            '''
            geo_name = geo.replace('ShapeOrig', '')
            geo_list.append(geo_name)
    if not geo_list:
        geo_list = cmds.ls(type='surfaceShape')
    return geo_list

def getJointDict(root):
    joint_pos = {}
    this_level = [root]
    while this_level:
        next_level = []
        for p_node in this_level:
            jpos = cmds.xform( p_node, query=True, translation=True, worldSpace=True )
            joint_pos[p_node] = {}
            joint_pos[p_node]['pos'] = jpos
            joint_pos[p_node]['ch'] = []
            ch_list = cmds.listRelatives(p_node, children=True, type='joint')
            pa_list = cmds.listRelatives(p_node, parent=True, type='joint')
            if ch_list is not None:
                joint_pos[p_node]['ch'] += ch_list
                next_level += ch_list
            if pa_list is not None:
                joint_pos[p_node]['pa'] = pa_list[0]
            else:
                joint_pos[p_node]['pa'] = 'None'
        this_level = next_level
    return joint_pos

def record_info(root, jointDict, geo_name, file_info):
    for key, val in jointDict.items():
        file_info.write('joints {0} {1:.8f} {2:.8f} {3:.8f}\n'.format(key, val['pos'][0], val['pos'][1], val['pos'][2]))
    file_info.write('root {}\n'.format(root))
    vtxIndexList = cmds.getAttr(geo_name + ".vrts", multiIndices=True)
    for i in vtxIndexList:
        w_array = cmds.skinPercent('skinCluster1', geo_name + ".vtx[" + str(i) + "]", query=True, value=True, normalize=True)
        jname_array = mel.eval('skinCluster -query -inf skinCluster1')
        if abs(1 - np.sum(w_array)) > 1e-5:
            exit(0)
        cur_line = 'skin {0} '.format(i)
        for cur_j in range(len(jname_array)):
            if w_array[cur_j] > 0:
                cur_line += '{0} {1:.4f} '.format(jname_array[cur_j], w_array[cur_j])
        cur_line += '\n'
        file_info.write(cur_line)
    for key, val in jointDict.items():
        if val['pa'] != 'None':
            file_info.write('hier {0} {1}\n'.format(val['pa'], key))
    
def record_obj(root, geoList, file_obj, obj_name):
    start_v_number = 1
    # save texture map, obj, mtl to intermediate files 
    cmds.select(geoList[0]) # select a mesh.
    output_filename = os.path.splitext(obj_name)[0] + '_intermediate.obj'
    cmds.file(output_filename, force=True, op="groups=0;ptgroups=0;materials=1;smoothing=0;normals=1", typ="OBJexport", pr=True, es=True) # save the selected mesh to OBJ file   vtxIndexList = cmds.getAttr(geo + ".vrts", multiIndices=True)
    cmds.select(clear=True)

    for geo in geoList:
        vtxIndexList = cmds.getAttr(geo + ".vrts", multiIndices=True)
        for i in vtxIndexList:
            pos = cmds.xform( geo + ".vtx[" + str(i) + "]", query=True, translation=True, worldSpace=True )
            new_line = "v {:f} {:f} {:f}\n".format(pos[0], pos[1], pos[2])
            file_obj.write(new_line)
        faceIndexList = cmds.getAttr(geo + ".face", multiIndices=True)
        for i in faceIndexList:
            cmds.select(geo + ".f["+ str(i) + "]", r=True)
            fv = cmds.polyInfo(fv=True)
            fv = fv[0].split()
            new_line = "f {:d} {:d} {:d}\n".format(int(fv[2]) + start_v_number, int(fv[3]) + start_v_number, int(fv[4]) + start_v_number)
            file_obj.write(new_line)
        start_v_number += len(vtxIndexList)

def loadInfo(info_name, geo_name):
    f_info = open(info_name,'r')
    joint_pos = {}
    joint_hier = {}
    joint_skin = []
    for line in f_info:
        word = line.split()
        if word[0] == 'joints':
            joint_pos[word[1]] = [float(word[2]),  float(word[3]), float(word[4])]
        if word[0] == 'root':
            root_pos = joint_pos[word[1]]
            root_name = word[1]
            cmds.joint(p=(root_pos[0], root_pos[1],root_pos[2]), name = root_name)
        if word[0] == 'hier':
            if word[1] not in joint_hier.keys():
                joint_hier[word[1]] = [word[2]]
            else:
                joint_hier[word[1]].append(word[2])
        if word[0] == 'skin':
            skin_item = word[1:]
            joint_skin.append(skin_item)
    f_info.close()
    
    this_level = [root_name]
    while this_level:
        next_level = []
        for p_node in this_level:
            if p_node in joint_hier.keys():
                for c_node in joint_hier[p_node]:
                    cmds.select(p_node, r=True)
                    child_pos = joint_pos[c_node]
                    cmds.joint(p=(child_pos[0], child_pos[1],child_pos[2]), name = c_node)
                    next_level.append(c_node)
        this_level = next_level         
    
    cmds.skinCluster( root_name, geo_name)
    #print len(joint_skin)
    for i in range(len(joint_skin)):
        vtx_name = geo_name + '.vtx['+joint_skin[i][0]+']'
        transValue = []
        for j in range(1,len(joint_skin[i]),2):
            transValue_item = (joint_skin[i][j], float(joint_skin[i][j+1]))
            transValue.append(transValue_item) 
        #print vtx_name, transValue
        cmds.skinPercent( 'skinCluster1', vtx_name, transformValue=transValue)
    cmds.skinPercent( 'skinCluster1', geo_name, pruneWeights=0.01, normalize=False )
    return root_name, joint_pos

if __name__ == '__main__':
    fbx_name = sys.argv[1]
    obj_name = fbx_name.replace(".fbx", ".obj") if len(sys.argv) < 3 else sys.argv[2]
    info_name = fbx_name.replace(".fbx", ".txt") if len(sys.argv) < 4 else sys.argv[3]

    # import fbx
    cmds.file(new=True, force=True)
    cmds.file(fbx_name, i=True, ignoreVersion=True, type='FBX', ra=True, mergeNamespacesOnClash=False, options="fbx", pr=True)
    cmds.select(clear=True)
    root_name = _getHierarchyRootJoint(cmds.ls(type='joint')[0])
    
    # export rig information as txt
    cmds.select(clear=True)
    root_name = _getHierarchyRootJoint(cmds.ls(type='joint')[0])
    jointDict = getJointDict(root_name)
    geoList = getGeometryGroups()
    
    # export obj
    with open(obj_name, 'w') as file_obj:
        record_obj(root_name, geoList, file_obj, obj_name)
    with open(info_name, 'w') as file_info:
        record_info(root_name, jointDict, geoList[0], file_info)
    
