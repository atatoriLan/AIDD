import time
import torch.nn.utils as U
import torch.optim as optim
from model import *
from tools import *
import argparse
# configuration
HYP = {
    'node_size': 100,
    'hid': 128,  # hidden size
    'epoch_num': 1000,  # epoch
    'batch_size': 512,  # batch size
    'lr_net': 0.004,  # lr for net generator 0.004
    'lr_dyn': 0.001,  # lr for dyn learner
    'lr_stru': 0.0001,  # lr for structural loss 0.0001 2000 0.01  0.00001
    'hard_sample': False,  # weather to use hard mode in gumbel
    'sample_time': 1,  # sample time while training
    'temp': 1,  # temperature
    'drop_frac': 1,  # temperature drop frac
}


parser = argparse.ArgumentParser()
parser.add_argument('--nodes', type=int, default=100, help='Number of nodes, default=10')
parser.add_argument('--network', type=str, default='ER', help='type of network')
parser.add_argument('--prediction_steps', type=int, default=10, help='prediction steps')
parser.add_argument('--sys', type=str, default='spring', help='simulated system to model,spring or cmn')
parser.add_argument('--dim', type=int, default=4, help='# information dimension of each node spring:4 cmn:1 ')
parser.add_argument('--exp_id', type=int, default=1, help='experiment_id, default=1')
parser.add_argument('--device_id', type=int, default=5, help='Gpu_id, default=5')
args = parser.parse_args()
#set gpu id
torch.cuda.set_device(args.device_id)
start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
print('start_time:', start_time)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
print('start_time:', start_time)


# model load  path
dyn_path = './model/dyn_spring_' + args.network + '_' + str(args.nodes) + 'pre_'+str(args.prediction_steps)+'_id' + str(args.exp_id) + '.pkl'
gen_path = './model/gen_spring_' + args.network + '_' + str(args.nodes) +'pre_'+str(args.prediction_steps)+ '_id' + str(args.exp_id) + '.pkl'


generator = torch.load(gen_path).to(device)
dyn_isom = torch.load(dyn_path).to(device)
# data
# load_data
if args.sys== 'spring':
    train_loader, val_loader, test_loader, object_matrix = load_spring_multi(batch_size=HYP['batch_size'],node_num=args.nodes,network=args.network,
                                                                             prediciton_steps=args.prediction_steps,exp_id=args.exp_id)

object_matrix = object_matrix.cpu().numpy()


def test_dyn_gen():
    loss_batch = []
    mse_batch = []

    print('current temp:', generator.temperature)

    for idx, data in enumerate(test_loader):
        print('batch idx:', idx)
        # data
        data = data.to(device)

        x = data[:, : ,0,:]
        y = data[:, :,1:, :]
        # drop temperature
        generator.drop_temp()
        outputs = torch.zeros(y.size(0), y.size(1), y.size(2)+1,y.size(3))

        outputs[:,:,0,:] = x
        temp_x = x

        num = int(args.nodes / HYP['node_size'])
        remainder = int(args.nodes  % HYP['node_size'])
        if remainder == 0:
            num = num - 1

        #multistep prediction
        for step in range(args.prediction_steps):
            cur_temp_x = temp_x
            for j in range(args.nodes ):
                # predict and caculate the loss
                adj_col = generator.sample_adj_i(j, hard=HYP['hard_sample'], sample_time=HYP['sample_time']).to(device)
                y_hat = dyn_isom(cur_temp_x, adj_col, j, num, HYP['node_size'])
                temp_x[:,j,:] = y_hat

            outputs[:,:,step+1,:] = temp_x


        loss = torch.mean(torch.abs(outputs[:,:,1:,:] - y.cpu()))


        loss_batch.append(loss.item())
        mse_batch.append(F.mse_loss(y.cpu(), outputs[:,:,1:,:]).item())

    # each item is the mean of all batches, means this indice for one epoch
    return np.mean(loss_batch), np.mean(mse_batch),


with torch.no_grad():
    loss, mse = test_dyn_gen()
    print('loss:' + str(loss) + ' mse:' + str(mse))




