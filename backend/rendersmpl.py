#!/usr/bin/env python
# coding=utf-8

import subprocess
import os, os.path as osp, glob, random
import numpy as np
from scipy.spatial.transform import Rotation as R
import open3d as o3d
try:
    import open3d.visualization as vis
    import open3d.visualization.rendering as rendering
except:
    pass
import json
import pickle as pkl
import matplotlib.pyplot as plt
from smpl_np import SMPLModel

def render_smpl_func(m, savepath):
    if osp.exists(savepath):    return 
    campos = np.array([0., 0., 2.1])
    # render = rendering.OffscreenRenderer(960, 540)
    render = rendering.OffscreenRenderer(560, 420)
    mat_body = vis.rendering.MaterialRecord()
    mat_body.shader = 'defaultLit'
    mat_body.base_color = [0.3, 0.3, 0.3, 1.0]
    m.compute_vertex_normals()
    render.scene.add_geometry('smpl', m, mat_body)
    render.setup_camera(72., np.zeros((3, )), campos, np.array([[0.], [1.], [0.]]))
    # render.scene.show_axes(True)
    render.scene.scene.set_sun_light([0., -0.3, -2.1], [1.0, 1.0, 1.0], 105000)
    render.scene.scene.enable_sun_light(True)
    img = render.render_to_image()
    img = np.asarray(img)
    # plt.imshow(img)
    if savepath is not None:
        plt.imsave(savepath, img)
        print('rendered smpl image saved to', savepath)
        plt.close()
    del img
    # plt.show()
    # plt.close()

render_smpl = int(o3d.__version__.split('.')[1]) > 11
saveroot = "./motion_frontcam/videos/"
os.makedirs(saveroot, exist_ok=True)
motion_files = glob.glob("./motion_frontcam/data/*.pkl")
for motion_file in motion_files:
    if 'info_seq_' in motion_file:
        os.rename(motion_file, motion_file.replace('info_seq_', ''))

motion_files = glob.glob("./motion_frontcam/data/*.pkl")
smpl_model = SMPLModel("./smpl_model.pkl")
smpl_mesh = o3d.geometry.TriangleMesh()
smpl_mesh.vertices = o3d.utility.Vector3dVector(smpl_model.verts)
smpl_mesh.triangles = o3d.utility.Vector3iVector(smpl_model.faces)
compose_cmd_template = "ffmpeg -n -f image2 -r 14 -i %04d.jpg {}"
maxlen = 200

for motion_file in motion_files:
    seq = pkl.load(open(motion_file, "rb"))
    joints_3d_gt = seq['joint_3d_gt'][:maxlen]
    trans = joints_3d_gt[:, 13:14][:maxlen]
    shapes, poses = seq['shape'][:maxlen], seq['pose'][:maxlen]

    savedir = osp.join(saveroot, osp.basename(motion_file).split('.')[0])
    os.makedirs(savedir, exist_ok=True)
    for index, (_shape, _pose, _trans) in enumerate(zip(shapes, poses, trans)):
        smpl_savepath = osp.join(savedir, "%04d.jpg" % index)
        shape, pose, joint_3d_gt = shapes[index], poses[index], joints_3d_gt[index]
        smpl_model.set_params(beta=_shape, pose=_pose, trans=_trans)
        smpl_model.update()
        rot = R.from_euler('x', 0, degrees=True)
        upside_down_verts = rot.apply(smpl_model.verts)
        smpl_mesh.vertices = o3d.utility.Vector3dVector(upside_down_verts)
        render_smpl_func(smpl_mesh, smpl_savepath)
    compose_cmd = compose_cmd_template.format("../" + osp.basename(savedir) + '.mp4')
    subprocess.call(compose_cmd, cwd=savedir, shell=True)
