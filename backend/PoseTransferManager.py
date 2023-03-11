import os, os.path as osp, time
import numpy as np 
import pickle as pkl 
import subprocess
import glob 
from obj_loader import TriangleMesh
from utils import lazy_get_model_to_smpl, parse_hier_from_riginfo_lines, clean_info, parse_joints_from_riginfo_lines, parse_skin_from_riginfo_lines, timer, get_extra_uv_lines, clean_mtl

def with_zeros(x):
    return np.vstack((x, np.array([[0.0, 0.0, 0.0, 1.0]])))

def pack(x): 
    return np.dstack((np.zeros((x.shape[0], 4, 3)), x))

def rodrigues(r):
    """
    util function which converts rotation vectors into rotation matrices
    """
    theta = np.linalg.norm(r, axis=(1, 2), keepdims=True)
    # avoid zero divide
    theta = np.maximum(theta, np.finfo(np.float64).eps)
    r_hat = r / theta
    cos = np.cos(theta)
    z_stick = np.zeros(theta.shape[0])
    m = np.dstack([
      z_stick, -r_hat[:, 0, 2], r_hat[:, 0, 1],
      r_hat[:, 0, 2], z_stick, -r_hat[:, 0, 0],
      -r_hat[:, 0, 1], r_hat[:, 0, 0], z_stick]
    ).reshape([-1, 3, 3])
    i_cube = np.broadcast_to(
      np.expand_dims(np.eye(3), axis=0),
      [theta.shape[0], 3, 3]
    )
    A = np.transpose(r_hat, axes=[0, 2, 1])
    B = r_hat
    dot = np.matmul(A, B)
    R = cos * i_cube + (1 - cos) * dot + np.sin(theta) * m
    return R

class PoseTransferManager:
    def __init__(self):
        self.fbx_parse_cmd_template = "mayapy fbx_parser.py {}"
        self.full_obj_path = None 
        self.minimal_obj_path = None
        self.riginfo_path = None 
        self.v_posed = self.index2joint = self.joint2index = self.joints = self.parent = self.id_to_col = None
        self.mesh_shared_lines = None
        # should create a random pose pool to sample from 
        self.pose_pool = self._build_pose_pool()

    def _build_pose_pool(self):
        path_to_load = "./posepool.npy"
        if not osp.exists(path_to_load):
            pkl_files = glob.glob("./motion_frontcam/*")
            poses = []
            for pkl_file in pkl_files:
                poses.append(pkl.load(open(pkl_file, "rb"))['pose'])
            poses = np.concatenate(poses, axis=0)
            np.save(path_to_load, poses)
        print('random poses loaded.')
        return np.load(path_to_load)

    def build_meta(self):
        if self.full_obj_path is None or not osp.exists(self.full_obj_path):
            print('can not find obj expected at path {}'.format(self.full_obj_path))
            return False 
        if self.riginfo_path is None or not osp.exists(self.riginfo_path):
            print('can not find riginfo expected at path {}'.format(self.riginfo_path))
            return False 
        
        lines = open(self.riginfo_path).readlines()
        # custom_inmesh = TriangleMesh(self.full_obj_path)
        custom_inmesh = TriangleMesh(self.minimal_obj_path)
        v_posed = custom_inmesh.vertices

        hier, joint2index, hier_lines = parse_hier_from_riginfo_lines(lines)
        if hier is None or joint2index is None:
            print('failed to parse a tree structure from fbx topology')
            return False 

        index2joint = {index: joint for joint, index in joint2index.items()}
        kinetree_table = [[-1, 0]]
        for k, v in hier.items(): 
            for vv in v:    kinetree_table.append([k, vv])
        kinetree_table = np.array(kinetree_table).reshape(-1, 2).T

        weights, skin_lines = parse_skin_from_riginfo_lines(lines, joint2index)

        # T-pose skeleton
        joints, joint_lines = parse_joints_from_riginfo_lines(lines, joint2index)

        # child to index
        id_to_col = {
            kinetree_table[1, i]: i for i in range(kinetree_table.shape[1])
        }
        parent = {
            i: id_to_col[kinetree_table[0, i]]  for i in range(1, kinetree_table.shape[1])
        }
        for name in ['v_posed', 'kinetree_table', 'joints', 'hier', 'weights', 
                     'id_to_col', 'parent', 'index2joint', 'joint2index', 
                     'hier_lines', 'skin_lines', 'joint_lines']:
            setattr(self, name, eval(name))
        return True 

    def parse_fbx(self, fbx_path):
        """
        use maya to parse the fbx model into obj, mtl and texture files
        should return the obj_path, txt_path, mtl_path
        """
        full_obj_path = fbx_path.replace(".fbx", "_intermediate.obj")
        mtl_path = fbx_path.replace(".fbx", "_intermediate.mtl")
        riginfo_path = fbx_path.replace(".fbx", ".txt")
        minimal_obj_path = fbx_path.replace(".fbx", ".obj")
        if osp.exists(full_obj_path) and osp.exists(riginfo_path) and osp.exists(minimal_obj_path):
            print('find already parsed obj and riginfo, skip')
        else:
            print('parsing fbx {} into obj and mtl files'.format(fbx_path))
            fbx_parse_cmd = self.fbx_parse_cmd_template.format(fbx_path)
            res = subprocess.run(fbx_parse_cmd, shell=True, capture_output=True)
            if res.returncode != 0 or not osp.exists(full_obj_path) or not osp.exists(riginfo_path):
                print('parse failure | incomplete parsing, abort.')
                return False 
        
        clean_info(riginfo_path)
        clean_mtl(mtl_path)
        self.full_obj_path = full_obj_path 
        self.riginfo_path = riginfo_path
        self.minimal_obj_path = minimal_obj_path
        self.mesh_shared_lines = get_extra_uv_lines(full_obj_path)
        return True 
         

    def match(self):
        """
        match between the fbx topology and smpl topology 
        matching methods: 
        1. lazy mapper, simply match via joint names 
        """
        if self.index2joint is None:
            print('pls first parse the fbx and build meta info to obtain index2joint mapping')
            return False 
        self.model_to_smpl = lazy_get_model_to_smpl(self.index2joint) 
        if len(self.model_to_smpl) < 10:
            print('lazy mapper only maps {} nodes successfully, abort'.format(len(self.model_to_smpl)))
            return False 
        print('lazy mapper maps {} nodes out of {} nodes'.format(len(self.model_to_smpl), len(self.index2joint.keys())))
        return True 

    def transfer_given_pose(self, human_pose):
        start = time.time()
        num_joints, _ = self.weights.shape[:2]
        poses = np.zeros((1, num_joints, 3), dtype=np.float32)
        model_to_smpl = lazy_get_model_to_smpl(self.index2joint)

        if len(model_to_smpl) < 10:
            return None, None

        for model_index, smpl_index in model_to_smpl.items(): 
            poses[:, model_index] = human_pose[smpl_index]

        R = rodrigues(poses.reshape(-1, 1, 3))

        # forward kinematics process, calculate along the kinematic chain
        G = np.empty((self.kinetree_table.shape[1], 4, 4))
        G[0] = with_zeros(np.hstack((R[0], self.joints[0, :].reshape([3, 1]))))
        for i in range(1, self.kinetree_table.shape[1]):
            G[i] = G[self.parent[i]].dot(
                with_zeros(
                    np.hstack(
                        [R[i],((self.joints[i, :]-self.joints[self.parent[i],:]).reshape([3,1]))]
                    )
                )
            )
        new_joints = G[:, :3, 3]
        # new_joint_lines = []
        # for idx, name in enumerate(list(self.joint2index.keys())): 
            # new_joint_lines.append("joints " + name + " {:.8f} {:.8f} {:.8f}".format(new_joints[idx, 0], new_joints[idx, 1], new_joints[idx, 2]))

        # obtain joint offset from T-pose
        G = G - pack(
        np.matmul(
            G,
            np.hstack([self.joints, np.zeros([num_joints, 1])]).reshape([num_joints, 4, 1])
            )
        )

        # linear blend skinning process, refer to SMPL paper for more details
        T = np.tensordot(self.weights.T, G, axes=[[1], [0]])
        rest_shape_h = np.hstack((self.v_posed, np.ones([self.v_posed.shape[0], 1])))
        try:    v = np.matmul(T, rest_shape_h.reshape([-1, 4, 1])).reshape([-1, 4])[:, :3]
        except: return None, None
        end = time.time()
        # print('transfer finished in {}s'.format(end - start))
        return v
    
    @timer
    def transfer_one_frame(self, human_pose):
        self._check_match()
        return self.transfer_given_pose(human_pose)

    @timer
    def transfer_one_sequence(self, human_poses, human_trans, save_root=None):
        self._check_match()
        if save_root is not None:   
            os.makedirs(save_root, exist_ok=True)
            # also create the symbolink, when save to a different directory 
            parent_dir = osp.dirname(osp.abspath(self.riginfo_path))
            if save_root != parent_dir:
                for _file in os.listdir(parent_dir): 
                    suffix = osp.splitext(_file)[1]
                    if suffix in ['.png', '.mtl', '.JPG', '.jpg', '.PNG']:
                        src_path = os.path.abspath(os.path.join(parent_dir, _file))
                        dst_path = os.path.join(save_root, _file)
                        print(src_path, dst_path)
                        if not osp.exists(dst_path): 
                            os.symlink(src_path, dst_path)

        for frame_id, (_human_pose, _human_trans) in enumerate(zip(human_poses, human_trans)):
            vposed = self.transfer_given_pose(_human_pose)
            vposed = vposed + _human_trans
            if save_root is not None:
                savepath = osp.join(save_root, str(frame_id) + '.obj')
                self.reassemble_posed_vertices(vposed, savepath)

    @timer 
    def reassemble_posed_vertices(self, vposed, savepath):
        if osp.exists(savepath):    return
        # pack posed vertices, faces, uvs, and all other information into one file
        out_objfile = savepath

        with open(out_objfile, 'w') as fp:
            for v in np.asarray(vposed):
                fp.write('v %f %f %f\n' % (v[0], v[1], v[2]))

            for uv_line in self.mesh_shared_lines: 
                fp.write(uv_line + '\n')

        print('reassembled file dumped to {}'.format(savepath))

    def sample_pose(self):
        index = np.random.randint(0, len(self.pose_pool))
        return self.pose_pool[index], index
    
    def _check_match(self):
        assert self.model_to_smpl is not None

if __name__ == '__main__':
    pose_transfer_manager = PoseTransferManager()
    pose_transfer_manager.parse_fbx("37.fbx")
    pose_transfer_manager.build_meta()
    pose_transfer_manager.match()
    random_pose, _ = pose_transfer_manager.sample_pose()
    pose_transfer_manager.transfer_one_frame(random_pose)
    sample_motion_file = "./motion_frontcam/info_seq_WalkTogether.pkl"
    sample_motion = pkl.load(open(sample_motion_file, "rb"))
    poses, joints_3d_gt = sample_motion['pose'], sample_motion['joint_3d_gt']
    trans = joints_3d_gt[:, 13:14]
    pose_transfer_manager.transfer_one_sequence(poses, trans, save_root='transfer')
