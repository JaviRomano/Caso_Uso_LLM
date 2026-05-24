import json
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer

class HotelResponseDataset(Dataset):
    def __init__(self, json_path: str, tokenizer, max_length: int = 256):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.data = []
        
        with open(json_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        
        for item in items:
            # Formato simple: "Opinión: {review}\nRespuesta: {response}"
            text = f"Opinión: {item['review_text']}\nRespuesta: {item['response']}"
            self.data.append(text)
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        text = self.data[idx]
        
        encoding = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt"
        )
        
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": encoding["input_ids"].squeeze().clone()
        }

def get_dataloader(json_path: str, tokenizer, batch_size: int = 8, max_length: int = 256):
    dataset = HotelResponseDataset(json_path, tokenizer)
    return DataLoader(dataset, batch_size=batch_size, shuffle=True)