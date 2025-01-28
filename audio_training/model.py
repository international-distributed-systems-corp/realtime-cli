import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from .storage import AudioStorage, AudioSample

class AudioDataset(Dataset):
    """Dataset for training speaker recognition model"""
    
    def __init__(self, storage: AudioStorage):
        self.storage = storage
        self.samples = []
        self._load_samples()
        
    def _load_samples(self):
        """Load all samples from storage"""
        # Get samples for both speakers
        user_samples = self.storage.get_samples_by_speaker('user')
        agent_samples = self.storage.get_samples_by_speaker('agent')
        
        self.samples = user_samples + agent_samples
        
    def __len__(self):
        return len(self.samples)
        
    def __getitem__(self, idx):
        sample = self.samples[idx]
        # Convert audio bytes to tensor
        audio_tensor = torch.from_numpy(
            np.frombuffer(sample.audio_data, dtype=np.int16)
        ).float()
        
        # Create label (0 for user, 1 for agent)
        label = torch.tensor(1.0 if sample.speaker == 'agent' else 0.0)
        
        return audio_tensor, label

class SpeakerRecognitionModel(nn.Module):
    """Simple CNN for speaker recognition"""
    
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 64, 3)
        self.conv2 = nn.Conv1d(64, 64, 3)
        self.pool = nn.MaxPool1d(2)
        self.fc1 = nn.Linear(64 * 8, 64)
        self.fc2 = nn.Linear(64, 1)
        
    def forward(self, x):
        # Add channel dimension
        x = x.unsqueeze(1)
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 64 * 8)
        x = F.relu(self.fc1(x))
        x = torch.sigmoid(self.fc2(x))
        return x

def train_model(storage: AudioStorage, 
                epochs: int = 10,
                batch_size: int = 32,
                learning_rate: float = 0.001):
    """Train the speaker recognition model"""
    
    dataset = AudioDataset(storage)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    model = SpeakerRecognitionModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.BCELoss()
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch_audio, batch_labels in dataloader:
            optimizer.zero_grad()
            outputs = model(batch_audio)
            loss = criterion(outputs, batch_labels)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
        
    return model
