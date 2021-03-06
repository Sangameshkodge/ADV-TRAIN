""""""
"""
@authors: Deepak Ravikumar Tatachar, Sangamesh Kodge
@copyright: Nanoelectronics Research Laboratory
"""
""""""
import sys
sys.path.append('../')

import torch
from torch.utils.tensorboard import SummaryWriter
from advtrain.framework import Framework
from advtrain.instantiate_model import instantiate_model
from advtrain.utils.str2bool import str2bool
import argparse

####Terminal command for tensorboard(run in remote)
# tensorboard --logdir=./pretrained/imagenet/runs/<model_name> port=6006
####If running remotely use(run on local)
# ssh -NfL localhost:16006:localhost:6006 <username>@<remoteserver>
parser = argparse.ArgumentParser(description='Train', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
#training parameters
parser.add_argument('--epochs',                 default=100,                type=int,       help='Set number of epochs')
parser.add_argument('--dataset',                default='CIFAR10',          type=str,       help='Set dataset to use')
parser.add_argument('--parallel',               default=False,              type=str2bool,  help='Device in  parallel')
parser.add_argument('--gpu_id',               default='0,1,2,3',              type=str,  help='Device in  parallel')
parser.add_argument('--lr',                     default=0.01,               type=float,     help='Learning Rate')
parser.add_argument('--test_accuracy_display',  default=10,                 type=int,       help='Intervals to display test accuracy')
parser.add_argument('--optimizer',              default='SGD',              type=str,       help='Optimizer for training')
parser.add_argument('--loss',                   default='crossentropy',     type=str,       help='loss function for training')
parser.add_argument('--resume',                 default=False,              type=str2bool,  help='resume training from a saved checkpoint')
parser.add_argument('--include_validation',     default=False,              type=str2bool,  help='retrains with validation set')

# Dataloader args
parser.add_argument('--train_batch_size',       default=512,    type=int,       help='Train batch size')
parser.add_argument('--test_batch_size',        default=512,    type=int,       help='Test batch size')
parser.add_argument('--val_split',              default=0.1,    type=float,     help='fraction of training dataset split as validation')
parser.add_argument('--augment',                default=True,   type=str2bool,  help='Random horizontal flip and random crop')
parser.add_argument('--padding_crop',           default=4,      type=int,       help='Padding for random crop')
parser.add_argument('--shuffle',                default=True,   type=str2bool,  help='Shuffle the training dataset')
parser.add_argument('--random_seed',            default=None,   type=int,       help='initialising the seed for reproducibility')

# Model parameters
parser.add_argument('--suffix',         default='',         type=str,        help='appended to model name')
parser.add_argument('--arch',           default='resnet',   type=str,        help='Network architecture')
parser.add_argument('--pretrained',     default=False,      type=str2bool,   help='load saved model for ./pretrained/dataset/')
parser.add_argument('--torch_weights',  default=False,      type=str2bool,   help='load torchvison weights for imagenet')
parser.add_argument('--input_quant',    default=None,       type=str,       help='Quantization transfer function-Q1 Q2 Q4 Q6 Q8 HT FP')
parser.add_argument('--dorefa',         default=False,      type=str2bool,  help='Use Dorefa Net')
parser.add_argument('--qout',           default=False,      type=str2bool,  help='Output layer weight quantisation')
parser.add_argument('--qin',            default=False,      type=str2bool,  help='Input layer weight quantisation')
parser.add_argument('--abit',           default=32,         type=int,       help='activation quantisation precision')
parser.add_argument('--wbit',           default=32,         type=int,       help='Weight quantisation precision')
parser.add_argument('--normalize',           default=None,         type=int,       help='Normalise the data if not none')

# Attack parameters
parser.add_argument('--adv_trn',    default=False,      type=str2bool,  help='adv Training')
parser.add_argument('--attack',     default='PGD',      type=str,       help='Type of attack [PGD, CW]')
parser.add_argument('--lib',        default='custom',   type=str,       help='Use [foolbox, advtorch, custom] code for adversarial attack')
parser.add_argument('--use_bpda',   default=True,       type=str2bool,  help='Use Backward Pass through Differential Approximation when using attack')
parser.add_argument('--random',     default=True,       type=str2bool,  help='Random seed/strating points')
parser.add_argument('--iterations', default=40,         type=int,       help='Number of iterations of PGD')
parser.add_argument('--epsilon',    default=0.031,      type=float,     help='epsilon for PGD')
parser.add_argument('--targeted',   default=None,       type=int,       help='Target class for targeted attack, None for non targeted attack')
parser.add_argument('--stepsize',   default=0.01,       type=float,     help='stepsize for attack')

global args
args = parser.parse_args()
print(args)
if args.parallel:
    gpu_id = args.gpu_id.split(',')
    gpu_id = [int(i) for i in gpu_id]
else:
    gpu_id=[0,1,2,3]

def epoch_hook(framework):
    if args.dataset.lower() !='imagenet' and  args.dataset.lower() !='tinyimagenet' : 
        if (framework.current_epoch+1)%args.test_accuracy_display==0:
            print("\nEpoch {}: \n Train Loss:{} \n Train Accuracy:{} \n Test Accuracy:{} ".format(framework.current_epoch+1, framework.current_train_loss, framework.current_train_acc, framework.current_test_acc) )
    else:
        print("Epoch {}: \n Train Loss:{} \n Train Accuracy:{} \n Test Accuracy:{} \n\n".format(framework.current_epoch+1, framework.current_train_loss, framework.current_train_acc, framework.current_test_acc) )
    
    writer.add_scalars('Accuracy',
                    {'train':framework.current_train_acc,
                    'val'   :framework.current_val_acc,
                    'test'  :framework.current_test_acc,
                    },framework.current_epoch)

def batch_hook(framework):
    if args.dataset.lower() =='imagenet' or  args.dataset.lower() =='tinyimagenet' : 
        if (framework.current_batch+1)%args.test_accuracy_display==0:
            print("Epoch{}-Batch{}:  Train Loss:{}  Train Accuracy:{} ".format(framework.current_epoch+1,framework.current_batch+1, framework.current_train_loss, framework.current_train_acc) )
    else:
        pass
    
    writer.add_scalars('Loss',
                    {'train':framework.current_train_loss,
                    'val'   :framework.current_val_loss,
                    },
                    framework.current_epoch + framework.current_batch/framework.no_of_batches_train)
    
    
if args.dataset.lower()=='imagenet':
    num_classes=1000
elif  args.dataset.lower()=='tinyimagenet':
    num_classes=200
elif  args.dataset.lower()=='cifar100':
    num_classes=100
else:
    num_classes=10

net, model_name, Q = instantiate_model(dataset=args.dataset,
                                    num_classes=num_classes,
                                    input_quant=args.input_quant, 
                                    arch=args.arch,
                                    dorefa=args.dorefa,
                                    abit=args.abit,
                                    wbit=args.wbit,
                                    qin=args.qin,
                                    qout=args.qout,
                                    suffix=args.suffix, 
                                    load=args.pretrained,
                                    torch_weights=args.torch_weights,
                                    normalize= args.normalize)

# default `log_dir` is "runs" - we'll be more specific here
writer = SummaryWriter('./pretrained/'+args.dataset.lower()+'/runs/'+model_name)

framework = Framework(net=net,
                      model_name=model_name,
                      preprocess=Q,
                      dataset=args.dataset,
                      epochs=args.epochs,
                      train_batch_size=args.train_batch_size,
                      test_batch_size=args.test_batch_size,
                      val_split=args.val_split,
                      augment=args.augment,
                      padding_crop=args.padding_crop,
                      shuffle=args.shuffle,
                      random_seed=args.random_seed,
                      optimizer=args.optimizer,
                      loss=args.loss,
                      learning_rate=args.lr,
                      adversarial_training=args.adv_trn,
                      lib = args.lib,
                      attack=args.attack,
                      iterations=args.iterations,
                      epsilon=args.epsilon,
                      stepsize=args.stepsize,
                      use_bpda=args.use_bpda,
                      target=args.targeted,
                      random=args.random,
                      device=None,
                      normalize= args.normalize)

framework.train(epoch_hook=epoch_hook,
              resume_training=args.resume,
              batch_hook=batch_hook, 
              parallel=args.parallel,
              parallel_devices_ids=gpu_id)

_ , _, accuracy = framework.test()
print('Test Acc: {}'.format(accuracy))
print("Confidence correct : {} \nConfidence incorrect : {} \nConfusion Matrix:\n{}".format(framework.confidence_correct,framework.confidence_incorrect, framework.confusion_matrix))
writer.close()