#!/usr/bin/env python

"""
Example script to register two volumes with VoxelMorph models.

Please make sure to use trained models appropriately. Let's say we have a model trained to register 
a scan (moving) to an atlas (fixed). To register a scan to the atlas and save the warp field, run:

    register.py --moving moving.nii.gz --fixed fixed.nii.gz --model model.pt 
        --moved moved.nii.gz --warp warp.nii.gz

The source and target input images are expected to be affinely registered.

If you use this code, please cite the following, and read function docs for further info/citations
    VoxelMorph: A Learning Framework for Deformable Medical Image Registration 
    G. Balakrishnan, A. Zhao, M. R. Sabuncu, J. Guttag, A.V. Dalca. 
    IEEE TMI: Transactions on Medical Imaging. 38(8). pp 1788-1800. 2019. 

    or

    Unsupervised Learning for Probabilistic Diffeomorphic Registration for Images and Surfaces
    A.V. Dalca, G. Balakrishnan, J. Guttag, M.R. Sabuncu. 
    MedIA: Medical Image Analysis. (57). pp 226-236, 2019 

Copyright 2020 Adrian V. Dalca

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in 
compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or 
implied. See the License for the specific language governing permissions and limitations under 
the License.
"""

import os
import argparse

# third party
import numpy as np
import nibabel as nib
import torch

# import voxelmorph with pytorch backend
os.environ['VXM_BACKEND'] = 'pytorch'
import voxelmorph as vxm   # nopep8

# parse commandline args
parser = argparse.ArgumentParser()
parser.add_argument('--moving', required=True, help='moving image (source) filename')
parser.add_argument('--fixed', required=True, help='fixed image (target) filename')
parser.add_argument('--moved', required=True, help='warped image output filename')
parser.add_argument('--model', required=True, help='pytorch model for nonlinear registration')
parser.add_argument('--warp', help='output warp deformation filename')
parser.add_argument('-g', '--gpu', help='GPU number(s) - if not supplied, CPU is used')
parser.add_argument('--multichannel', action='store_true',
                    help='specify that data has multiple channels')
args = parser.parse_args()

# device handling
if args.gpu and (args.gpu != '-1'):
    device = 'cuda'
    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
else:
    device = 'cpu'
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

# load and set up model
model = vxm.networks.VxmDense.load(args.model, device)
model.to(device)
model.eval()
# load moving and fixed images
add_feat_axis = not args.multichannel
vols, fixed_affine = vxm.py.utils.load_volfile(args.moving, add_batch_axis=True, add_feat_axis=add_feat_axis, ret_affine=True)

output_moved = []
output_warp = []
[_, slices, x, y, _] = vols.shape
input_fixed = torch.from_numpy(vols[:, 0, :, :, :]).to(device).float().permute(0, 3, 1, 2)
# print(input_fixed.shape)
output_moved = [input_fixed.squeeze()]
output_warp = []
for slice in range(slices-1):
    # set up tensors and permute
    # TODO: check the dimension 
    input_moving = torch.from_numpy(vols[:, slice+1, :, :, :]).to(device).float().permute(0, 3, 1, 2)
    moved, warp = model(input_moving, input_fixed, registration=True)
    # print(f"move {moved.shape}")
    output_moved.append(moved.detach().cpu().numpy().squeeze())
    output_warp.append(warp.detach().cpu().numpy().squeeze())

moved = np.stack(output_moved)
warp = np.stack(output_warp)

if args.moved:
    vxm.py.utils.save_volfile(moved, args.moved, fixed_affine)

# save warp
if args.warp:
    print(warp.shape)
    vxm.py.utils.save_volfile(warp[:, 0, :, :], args.warp, fixed_affine)

# vxm.py.utils.save_volfile(np.squeeze(vols), 'data/data_output/0003_rawimages_slice_0_original.nii')

