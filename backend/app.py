import os, os.path as osp, glob, subprocess
import hashlib, time 
import pickle as pkl 
from flask_cors import CORS
from flask import Flask, jsonify, request, make_response, send_from_directory
from PoseTransferManager import PoseTransferManager

port = os.environ['SMPLCARTOON_PORT'] if 'SMPLCARTOON_PORT' in os.environ else 5905
public_ip = 'http://121.5.67.94:{}'.format(port)
public_ip = 'http://127.0.0.1:5000'

motion_root = "./motion_frontcam"
motion_video_dir = osp.join(motion_root, "videos")
motion_data_dir = osp.join(motion_root, "data")

work_root = "service"
os.makedirs(work_root, exist_ok=True)
app = Flask(__name__)
CORS(app)

headers = {
    'Access-Control-Allow-Origin': '*', 
    'Access-Control-Allow-Methods': '*'
}

ptm = PoseTransferManager()
maxlen = 200

def localpath2webpath(localpath):
    if not osp.isfile(localpath):
        return public_ip + '/static/' + localpath.strip('./') + '/'   # e.g. http://127.0.0.1:5000/static/service/abcdef/sample.fbx
    return public_ip + '/static/' + localpath.strip('./')   # e.g. http://127.0.0.1:5000/static/service/abcdef/sample.fbx

def webpath2localpath(webpath):
    index = webpath.find(work_root)
    return webpath[index:]

# @app.route('/motion', methods=['GET']):


@app.route('/getSequenceNames', methods=['GET'])
def getSequenceNames():
    # obtain dynamically to address refreshing or updating 
    motion_video_names = glob.glob(osp.join(motion_video_dir, "*.mp4"))
    sequence_names =  [osp.basename(motion_video_name).split('.')[0].replace('"', '').replace("'", "") for motion_video_name in motion_video_names]
    sequence_names = str(sequence_names).replace('"', '').replace("'", "").replace(" ", "")
    msg = jsonify(sequence_names)
    response = make_response(msg, 200)
    response.headers = headers 
    return response

@app.route('/uploadFBXModel', methods=['POST'])
def uploadFBXModel():
    print('here to upload')
    fbx_model = request.files['fbx_model'] 
    # obtain the hashsum as session id 
    timestamp = int(time.time()) * 100.
    temp_savepath = osp.join(work_root, str(timestamp))
    fbx_model.save(temp_savepath)

    md5h = hashlib.md5()
    with open(temp_savepath, 'rb') as f:
        while b:= f.read(8192):
            md5h.update(b)
    md5val = md5h.hexdigest()

    work_dir = osp.join(work_root, md5val)
    os.makedirs(work_dir, exist_ok=True)
    fbx_path = osp.join(work_dir, "sample.fbx")
    # print(osp.getsize(temp_savepath))
    if not osp.exists(fbx_path):    os.rename(temp_savepath, fbx_path)
    # print(osp.getsize(fbx_path))
    # os.remove(temp_savepath)
    print('temp modelfile deleted and real modelfile saved to', fbx_path)

    msg = jsonify(localpath2webpath(fbx_path))
    rep = make_response(msg, 200)
    rep.headers = headers
    return rep
    # pass     

@app.route('/downloadResources', methods=['POST'])
def downloadResources():
    download_mode = int(request.form['mode'])
    sequence_name = request.form['sequenceName']
    fbx_path = webpath2localpath(request.form['fbxPath'])
    work_dir = osp.dirname(fbx_path)
    zip_path = osp.join(work_dir, "{}.zip".format(int(time.time()) * 100))
    # import ipdb; ipdb.set_trace()
    if download_mode == 0:  zip_cmd = "zip -r {} -- *.mtl *.png *.jpg *.fbx *.obj *.txt".format(osp.basename(zip_path))
    else:   zip_cmd = "zip -r {} -- *.mtl *.png *.jpg *.fbx *.obj *.txt {}".format(osp.basename(zip_path), sequence_name) 
    print('running zip command', zip_cmd)
    zip_res = subprocess.run(zip_cmd, shell=True, capture_output=True, cwd=work_dir)
    print(zip_res.stdout)
    url = localpath2webpath(zip_path)
    print('zipfile saved and export to url', url)
    msg = jsonify(url)
    rep = make_response(msg, 200)
    rep.headers = headers
    return rep 

@app.route('/transfer', methods=['POST'])
def transfer():
    transfer_mode = request.form['mode']    # random, or sequence
    sequence_name = request.form['sequenceName']    # e.g. Walk_together0
    fbx_path = webpath2localpath(request.form['fbxPath'].strip('\n').strip('\r').strip('"').strip("'"))
    work_dir = osp.dirname(fbx_path) + '/'
    print('working directory', work_dir)

    ptm.parse_fbx(fbx_path)
    ptm.build_meta()
    ptm.match()
    if transfer_mode == 'random':
        human_pose, random_index = ptm.sample_pose()
        vposed = ptm.transfer_one_frame(human_pose)
        savepath = osp.join(work_dir, "random_{}.obj".format(random_index))
        ptm.reassemble_posed_vertices(vposed, savepath=savepath)
        return_data = {
            # "objPath": [localpath2webpath(savepath)], 
            "objPath": [osp.basename(savepath)], 
            "objDirectory": localpath2webpath(work_dir), 
            #"mtlName": localpath2webpath(fbx_path.replace(".fbx", "_intermediate.mtl"))
            "mtlName": osp.basename(fbx_path.replace(".fbx", "_intermediate.mtl"))
        }
        msg = jsonify(return_data)
        response = make_response(msg, 200)
        response.headers = headers 
    elif transfer_mode == 'sequence':
        sequence_dat = pkl.load(open(osp.join(motion_data_dir, sequence_name + '.pkl'), 'rb'))
        poses, joints_3d_gt = sequence_dat['pose'][:maxlen], sequence_dat['joint_3d_gt'][:maxlen]
        trans = joints_3d_gt[:, 13:14][:maxlen]
        # possibly reassemble and save 
        savedir = osp.join(work_dir, sequence_name)
        ptm.transfer_one_sequence(poses, trans, save_root=savedir)
        # ptm.reassemble_posed_vertices(vposed, savedir)
        sequence_obj_paths = glob.glob(osp.join(savedir, "*.obj"))
        sequence_obj_paths = sorted(sequence_obj_paths, key=lambda x: int(osp.basename(x).split('.')[0]))
        # msg = jsonify(str([localpath2webpath(localpath) for localpath in sequence_obj_paths]))
        return_data = {
            # "objPath": [localpath2webpath(savepath) for savepath in sequence_obj_paths], 
            "objPath": [osp.basename(savepath) for savepath in sequence_obj_paths], 
            "objDirectory": localpath2webpath(savedir), 
            # "mtlName": localpath2webpath(fbx_path.replace(".fbx", "_intermediate.mtl"))
            "mtlName": osp.basename(fbx_path.replace(".fbx", "_intermediate.mtl"))
        }
        msg = jsonify(return_data)
        response = make_response(msg, 200)
        response.headers = headers
    else:
        # raise NotImplementedError()
        response = jsonify("")
    return response

if __name__ == '__main__':
    app.run()
