# -*- coding: utf-8 -*-
"""localGANtest.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1hbz3Yun0dALBsj72rkRWRsPR3EaCj9EA
"""

import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
import torchvision.datasets as dset
import matplotlib.pyplot as plt
import numpy as np
import os
import tarfile
import shutil
import requests
from torchvision.datasets import ImageFolder

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
torch.cuda.empty_cache()

def download_xray_dataset(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(save_path, 'wb') as fd:
        for chunk in response.iter_content(chunk_size=128):
            fd.write(chunk)

def extract_dataset(filename):
    with tarfile.open(filename, 'r:gz') as tar:
        tar.extractall('./data')

# List of datasets URLs. Add or modify based on your needs, can grab from https://github.com/toniesteves/covid19-chest-x-ray-detection/issues/1
dataset_urls = [
    'https://nihcc.box.com/shared/static/vfk49d74nhbxq3nqjg0900w5nvkorp5c.gz',
    'https://nihcc.box.com/shared/static/i28rlmbvmfjbl8p2n3ril0pptcmcu9d1.gz',
    'https://nihcc.box.com/shared/static/f1t00wrtdk94satdfb9olcolqx20z2jp.gz',
    'https://nihcc.box.com/shared/static/0aowwzs5lhjrceb3qp67ahp0rd1l1etg.gz',
    'https://nihcc.box.com/shared/static/v5e3goj22zr6h8tzualxfsqlqaygfbsn.gz',
    'https://nihcc.box.com/shared/static/asi7ikud9jwnkrnkj99jnpfkjdes7l6l.gz'
    # Add more URLs here...
]

# Download and extract each dataset
for url in dataset_urls:
    dataset_file = url.split("/")[-1]  # Extracts 'data_part1.tar.gz' from the URL for instance
    if not os.path.exists(dataset_file):
        download_xray_dataset(url, dataset_file)
        extract_dataset(dataset_file)

if not os.path.exists('./data/images/real_images'):
    os.makedirs('./data/images/real_images')

# Move all the images to the 'real_images' directory
for img_file in os.listdir('./data/images'):
    if img_file.endswith('.png'):
        shutil.move(os.path.join('./data/images', img_file), './data/images/real_images')

transform = transforms.Compose([
    transforms.Resize((1024, 1024)),  # You might need to change this depending on your GAN architecture
    transforms.Grayscale(num_output_channels=1),  # Convert to grayscale
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])

dataset = ImageFolder(root='./data/images', transform=transform)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=32, shuffle=True)

# Weight clipping function to be used later during training
def weight_clipping(m):
    if isinstance(m, nn.Conv2d) or isinstance(m, nn.Linear):
        m.weight.data.clamp_(-0.01, 0.01)

class ResidualBlockUp(nn.Module):
    def __init__(self, in_channels, out_channels, stride=2):
        super(ResidualBlockUp, self).__init__()

        self.main = nn.Sequential(
            nn.ConvTranspose2d(in_channels, out_channels, 4, stride=stride, padding=1, output_padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels)
        )

        self.shortcut = nn.Sequential()
        if in_channels != out_channels or stride != 1:
            self.shortcut = nn.Sequential(
                nn.ConvTranspose2d(in_channels, out_channels, 4, stride=stride, padding=1, output_padding=1),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        return nn.ReLU(inplace=True)(self.main(x) + self.shortcut(x))


class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()
        self.model = nn.Sequential(
            nn.ConvTranspose2d(100, 1024, 4, 1, 0),  # 4x4
            nn.BatchNorm2d(1024),
            nn.ReLU(True),

            ResidualBlockUp(1024, 512, stride=2),  # 8x8
            ResidualBlockUp(512, 256, stride=2),  # 16x16
            ResidualBlockUp(256, 128, stride=2),  # 32x32
            ResidualBlockUp(128, 64, stride=2),   # 64x64
            ResidualBlockUp(64, 32, stride=2),    # 128x128
            ResidualBlockUp(32, 16, stride=2),    # 256x256
            ResidualBlockUp(16, 8, stride=2),     # 512x512

            nn.ConvTranspose2d(8, 1, 4, 2, 1),    # 1024x1024
            nn.Tanh()
        )

    def forward(self, x):
        return self.model(x)


class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()
        self.main = nn.Sequential(
            nn.Conv2d(1, 4, 4, 2, 1, bias=False),  # 512x512
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(4, 8, 4, 2, 1, bias=False),  # 256x256
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(8, 16, 4, 2, 1, bias=False), # 128x128
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(16, 32, 4, 2, 1, bias=False), # 64x64
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(32, 64, 4, 2, 1, bias=False), # 32x32
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(64, 128, 4, 2, 1, bias=False), # 16x16
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(128, 256, 4, 2, 1, bias=False), # 8x8
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(256, 512, 4, 2, 1, bias=False), # 4x4
            nn.LeakyReLU(0.2, inplace=True),

            nn.Flatten(),
            nn.Linear(512*4*4, 1)
        )

    def forward(self, input):
        return self.main(input).squeeze()





generator = Generator().to(device)
discriminator = Discriminator().to(device)


# Loss and Optimizers
criterion = nn.BCELoss()
optimizer_g = torch.optim.Adam(generator.parameters(), lr=0.0005)
optimizer_d = torch.optim.Adam(discriminator.parameters(), lr=0.0005)


# Number of epochs
num_epochs = 25

# Lists to keep track of progress
img_list = []
G_losses = []
D_losses = []

# Training Loop
print("Starting Training")
for epoch in range(num_epochs):

    for i, data in enumerate(dataloader, 0):

        # Train the discriminator more often than the generator
        for _ in range(5):
            ## (1) Update Discriminator
            discriminator.zero_grad()

            real_images = data[0].to(device)
            b_size = real_images.size(0)

            # Loss for real images
            d_loss_real = -torch.mean(discriminator(real_images))

            # Loss for fake images
            noise = torch.randn(b_size, 100, 1, 1).to(device)
            fake_images = generator(noise)
            d_loss_fake = torch.mean(discriminator(fake_images.detach()))

            # Combined discriminator loss
            d_loss = d_loss_real + d_loss_fake
            d_loss.backward()
            optimizer_d.step()

            # Weight clipping for the discriminator
            discriminator.apply(weight_clipping)

        ## (2) Update Generator
        generator.zero_grad()

        # Generator's loss
        output = discriminator(fake_images)
        g_loss = -torch.mean(output)
        g_loss.backward()
        optimizer_g.step()

        # Print stats
        if i % 5 == 0:
            print(f"[{epoch}/{num_epochs}] [{i}/{len(dataloader)}] D_loss: {d_loss.item()} | G_loss: {g_loss.item()}")

        # Save losses for plotting later
        G_losses.append(g_loss.item())
        D_losses.append(d_loss.item())

    # Save and display generator's output after each epoch
    with torch.no_grad():
        fake_images = generator(noise).detach().cpu()
    img_list.append(torchvision.utils.make_grid(fake_images, padding=2, normalize=True))

    # Display the images
    plt.figure(figsize=(10,10))
    plt.axis("off")
    plt.title(f"Generated Images at Epoch {epoch}")
    plt.imshow(np.transpose(img_list[-1], (1,2,0)), cmap='gray')
    plt.show()

print("Finished Training")

# Visualize the GAN's progression (last epoch result)
plt.figure(figsize=(10,10))
plt.axis("off")
plt.imshow(np.transpose(img_list[-1], (1,2,0)))
plt.show()