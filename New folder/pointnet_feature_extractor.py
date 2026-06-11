import torch
import torch.nn as nn
import numpy as np
from torch_geometric.nn import PointNetConv, fps, radius, knn_interpolate
from torch_geometric.data import Batch

def make_mlp(in_channels, out_channels_list):
    layers = []
    for out_channels in out_channels_list:
        layers.append(nn.Linear(in_channels, out_channels))
        layers.append(nn.ReLU())
        layers.append(nn.BatchNorm1d(out_channels))
        in_channels = out_channels
    return nn.Sequential(*layers)

class SAModule(nn.Module):
    def __init__(self, ratio, r, nn_list):
        super().__init__()
        self.ratio = ratio
        self.r = r
        self.conv = PointNetConv(local_nn=nn_list)

    def forward(self, x, pos, batch):
        idx = fps(pos, batch, ratio=self.ratio)
        row, col = radius(pos, pos[idx], self.r, batch, batch[idx], max_num_neighbors=32)
        edge_index = torch.stack([col, row], dim=0)
        
        x_out = self.conv(x, (pos, pos[idx]), edge_index)
        pos_out = pos[idx]
        batch_out = batch[idx]
        return x_out, pos_out, batch_out

class FPModule(nn.Module):
    def __init__(self, k, nn_module):
        super().__init__()
        self.k = k
        self.nn = nn_module

    def forward(self, x, pos, batch, x_skip, pos_skip, batch_skip):
        x = knn_interpolate(x, pos, pos_skip, batch, batch_skip, k=self.k)
        if x_skip is not None:
            x = torch.cat([x, x_skip], dim=1)
        return self.nn(x)

class PointNetFeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        # SA layers
        # Layer 1: input has no features, so PointNetConv adds pos (3) automatically -> input to MLP is 3
        self.sa1 = SAModule(0.25, 1.0, make_mlp(3, [32, 64]))
        # Layer 2: input features (64) + pos (3) -> 67
        self.sa2 = SAModule(0.25, 2.5, make_mlp(64 + 3, [64, 128]))
        # Layer 3: input features (128) + pos (3) -> 131
        self.sa3 = SAModule(0.25, 5.0, make_mlp(128 + 3, [128, 256]))
        
        # FP layers (Feature Propagation / Upsampling)
        # FP3: upsample sa3 (256) to sa2 pos, concatenate with sa2 features (128) -> 384
        self.fp3 = FPModule(3, make_mlp(256 + 128, [256, 256]))
        # FP2: upsample fp3 (256) to sa1 pos, concatenate with sa1 features (64) -> 320
        self.fp2 = FPModule(3, make_mlp(256 + 64, [256, 128]))
        # FP1: upsample fp2 (128) to original pos, concatenate with original features (None/0) -> 128
        self.fp1 = FPModule(3, make_mlp(128, [128, 128, 128]))

    def forward(self, pos, batch):
        # SA forward pass
        x1, pos1, batch1 = self.sa1(None, pos, batch)
        x2, pos2, batch2 = self.sa2(x1, pos1, batch1)
        x3, pos3, batch3 = self.sa3(x2, pos2, batch2)
        
        # FP forward pass
        x = self.fp3(x3, pos3, batch3, x2, pos2, batch2)
        x = self.fp2(x, pos2, batch2, x1, pos1, batch1)
        x = self.fp1(x, pos1, batch1, None, pos, batch)
        
        return x

def extract_pointnet_features(xyz_np: np.ndarray,
                               batch_size: int = 4096,
                               device: str = None) -> np.ndarray:
    """
    Args:
        xyz_np: numpy array of shape (N, 3) — raw point coordinates
        batch_size: number of points per forward pass
    Returns:
        features: numpy array of shape (N, 128)
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
    model = PointNetFeatureExtractor().to(device)
    model.eval()
    
    num_points = xyz_np.shape[0]
    out_features = np.zeros((num_points, 128), dtype=np.float32)
    
    print(f"Extracting PointNet++ features for {num_points} points on {device}...")
    
    with torch.no_grad():
        for i in range(0, num_points, batch_size):
            end = min(i + batch_size, num_points)
            chunk = xyz_np[i:end]
            
            # Convert to PyG expected tensors
            pos_tensor = torch.tensor(chunk, dtype=torch.float32).to(device)
            # Batch tensor assigns all points in this chunk to the same "graph"
            batch_tensor = torch.zeros(chunk.shape[0], dtype=torch.long).to(device)
            
            features = model(pos_tensor, batch_tensor)
            out_features[i:end] = features.cpu().numpy()
            
    return out_features

# Quick local test if run directly
if __name__ == "__main__":
    test_xyz = np.random.rand(10000, 3)
    features = extract_pointnet_features(test_xyz)
    print(f"Successfully extracted features! Shape: {features.shape}")
