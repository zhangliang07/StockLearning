import torch
from torch import nn
import torch.nn.functional as functional
import numpy
from torchsummary import summary


class _PolicyCnnNetwork(nn.Module):
  def __init__(self, inputSize):
    super(_PolicyCnnNetwork, self).__init__()
    self.__flatten = nn.Flatten()
    self.__conv1 = nn.Sequential(
      nn.Conv1d(in_channels = inputSize, out_channels = 32, kernel_size=3, stride=1, padding=1),
      nn.ReLU(),
    )
    self.__conv2 =nn.Sequential(
      nn.Conv1d(32, out_channels = 128, kernel_size=3, stride=1, padding=1),
      nn.ReLU()
    )
    
    self.__linear1 =nn.Sequential(
      nn.Linear(3840, 256),
      nn.ReLU(),
    )
    self.__linear2 =nn.Sequential(
      nn.Linear(256, 3),
      nn.ReLU(),
    )
    return


  def forward(self, x):
    x = x.permute(0, 2, 1)
    x = self.__conv1(x)
    x = self.__conv2(x)
    x = self.__flatten(x)
    x = self.__linear1(x)
    x = self.__linear2(x)
    return x


#the most important is to write the currect loss function (convex function)
class _LossFunction(nn.Module):
  def __init__(self, type = 2):
    super(_LossFunction, self).__init__()
    self.__type = type
    self.__loss_fn = nn.CrossEntropyLoss()

    if type < 0 or type > 2: type = 2
    self.__fun = [self.__loss1, self.__loss2, self.__loss3]

    return


  # pred: shape(batchSize, 3)?? value(--, ++)
  # actions: (batchSize), value 0, 1 or 2
  # reward: (batchSize), value(--, ++)
  def forward(self, pred, actions, reward):
    return self.__fun[self.__type](pred, actions, reward)


  #this loss function seems NOT effective
  def __loss1(self, pred, actions, reward):
    reward.mul_(100)
    pred = pred.softmax(dim=1)
    actions.unsqueeze_(dim=1)
    actions_onehot = torch.zeros_like(pred)
    actions_onehot.scatter_(1, actions, 1)
    actions_onehot.softmax(dim = 1)

    #calculte the distance of two tensors
    temp = torch.abs(pred - actions_onehot)

    #as the distance is in [0, 1], calculate the inverse of the distance 
    temp = torch.sub(1, temp)
    temp = torch.sum(temp, dim=1)

    #the more they closer, the more effective of reward
    temp.mul_(reward)

    #get the exp(-x)
    temp = -temp;
    temp.exp_()

    #combine the batch
    loss = temp.sum()
    return loss


  #this seems effective
  def __loss2(self, pred, actions, reward):
    loss = self.__loss_fn(pred, actions, ).sub(1.0).mul(reward + 1.0)
    return loss


  #this seems effective
  def __loss3(self, pred, actions, reward):
    reward.mul_(100)
    pred = pred.softmax(dim=1)

    #calculte the distance of two tensors
    temp = functional.cross_entropy(pred, actions, reduce=False);
    temp = torch.sub(2.0, temp)

    #the more they closer, the more effective of reward
    temp.mul_(reward)

    #get the exp(-x)
    temp = -temp;
    #temp.exp_()   #i dont know the influence whether add it or not

    #combine the batch
    loss = temp.sum()
    return loss

  

class PolicyCnnNetwork:
  def __init__(self, inputSize):
    self.__device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using {} device".format(self.__device))
    self.model = _PolicyCnnNetwork(inputSize).to(self.__device)
    print(self.model);
    #summary(self.model, (30, 8))   #check the layers output size

    self.loss_fn = _LossFunction(2).to(self.__device)
    self.optimizer = torch.optim.SGD(self.model.parameters(), lr=1e-3);
    return


  # dataInput: shape(batchSize, windowSize, 8)?? value(--, ++)
  # actions: (batchSize), value 0, 1 or 2
  # reward: (batchSize), value(--, ++)
  def learn(self, dataInput, actions, reward, step):
    #reward should be a coefficient in (--, ++)
    #if rewead is 0.3, it means the final money is 1.3 times of original money
    #if rewead is -0.2, it means the final money is 0.8 times of original money
    #the more previous action is more important
    rewardList = [reward] * len(actions)
    for i in range(0, len(rewardList)):
      rewardList[i] = reward
      reward *= 0.98    #factor

    dataInput = torch.tensor(dataInput, device=self.__device)
    actions = torch.tensor(actions, device=self.__device)
    rewardList = torch.tensor(rewardList, device=self.__device)

    #Compute prediction error
    pred = self.model(dataInput)
    loss = self.loss_fn(pred, actions, rewardList)

    # Backpropagation
    self.optimizer.zero_grad()
    loss.backward()
    self.optimizer.step()
    return


  def predict(self, dataInput, randomRate):
    if numpy.random.random() > randomRate:
      dataInput = torch.tensor(dataInput).unsqueeze(0)
      dataInput = dataInput.to(self.__device)

      self.model.eval()
      pred = self.model(dataInput)
      predict = torch.argmax(pred, dim = 1).item()
    else:
      predict = numpy.random.randint(0, 3)

    return predict;