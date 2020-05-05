from dataloader import get_tweets_and_sentiment_label_loaders
from model import TransformerClassification
import torch
import torch.nn as nn
from torch import optim
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('-n', '--num_epochs', default=10)
args = parser.parse_args()
print(args)

# ネットワークの初期化を定義
def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        # init Linear Layer
        nn.init.kaiming_normal_(m.weight)
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)


def train_model(net, dataloaders_dict, criterion, optimizer, num_epochs):
    # use GPU if it is available
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("使用デバイス:{}".format(device))
    print('---------------start---------------')
    net.to(device)

    # ネットワークがある程度固定できれば高速化させる
    torch.backends.cudnn.benchmark = True

    # epochのループ
    for epoch in range(num_epochs):
        # epochごとの訓練と検証のループ
        for phase in ['train', 'val']:
            if phase == 'train':
                net.train() # modelをtrain modeに
            else:
                net.val() # modelをvalidation modeに

            epoch_loss = 0.0 # epcohの損失和
            epoch_corrects = 0

            # dataloaderからmini-batchを取り出すループ
            for batch in (dataloaders_dict[phase]):
                # batchはText1, Text2, Labelの辞書オブジェクト

                # use GPU if it is available
                inputs1 = batch.Text1[0].to(device)
                inputs2 = batch.Text2[0].to(device)
                labels = batch.Label.to(device)

                # optimizer初期化
                optimizer.zero_grad()

                # forward 計算
                with torch.set_grad_enabled(phase == 'train'):
                    # make mask
                    input_pad = 1 # 単語のIDで'<pad>: 1 より'
                    input_mask = (inputs1 != input_pad)

                    # Input to Transformer
                    outputs, _, _ = net(inputs1, input_mask)
                    loss = criterion(outputs, labels) # 損失計算
                    _, preds = torch.max(outputs, 1) #  Labelを予測

                    # 訓練時はバックプロパゲージョン
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                    # 結果計算
                    epoch_loss += loss.item() * inputs1.size(0) # lossの合計を計算
                    # 正解数の合計を計算
                    epoch_corrects += torch.sum(preds==labels.data)

            # epochごとのlossと正解率
            epoch_loss = epoch_loss / len(dataloaders_dict[phase].dataset)
            epoch_acc = epoch_corrects.double() / len(dataloaders_dict[phase].dataset)

            print('Epoch {}/{} | {:^5} | Loss:{:.4f} Acc: {:.4f}'.format(epoch+1, num_epochs, phase, epoch_loss, epoch_acc))

    return net

# データの読み込み
train_dl, val_dl, test_dl, TEXT1, TEXT2 = get_tweets_and_sentiment_label_loaders(max_length=256, batch_size=64)
# 辞書オブジェクトにまとめる
dataloaders_dict = {"train": train_dl, "val": val_dl}

# compose model
net = TransformerClassification(text_embedding_vectors=TEXT1.vocab.vectors, d_model=300, max_seq_len=256, output_dim=3)


# train mode
# TransformerBlockモジュールを初期化実行
net.net3_1.apply(weights_init)
net.net3_2.apply(weights_init)

# print("ネットワーク設定完了")

# 損失関数の設定
criterion = nn.CrossEntropyLoss()

# 最適化手法の設定
learning_rate = 2e-5
optimizer = optim.Adam(net.parameters(), lr=learning_rate)

# train, validationを実施
net_trained = train_model(net, dataloaders_dict, criterion, optimizer, num_epochs=args.num_epochs)



# eval mode
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu"):
net_trained.eval()
net_trained.to(device)

epoch_corrects = 0

for batch in (test_dl):

