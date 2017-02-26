'''SGD equivariance'''

import os
import sys
import time
sys.path.append('../')

import cv2
import input_data
import numpy as np
import skimage.io as skio
import tensorflow as tf

import models
import equivariant_loss as el

from matplotlib import pyplot as plt


def load_data():
	mnist = input_data.read_data_sets("/tmp/data/", one_hot=True)
	data = {}
	data['X'] = {'train': np.reshape(mnist.train._images, (-1,28,28,1)),
					 'valid': np.reshape(mnist.validation._images, (-1,28,28,1)),
					 'test': np.reshape(mnist.test._images, (-1,28,28,1))}
	data['Y'] = {'train': mnist.train._labels,
					 'valid': mnist.validation._labels,
					 'test': mnist.test._labels}
	return data


def random_sampler(n_data, opt, random=True):
	"""Return minibatched data"""
	if random:
		indices = np.random.permutation(n_data)
	else:
		indices = np.arange(n_data)
	mb_list = []
	for i in xrange(int(float(n_data)/opt['mb_size'])):
		mb_list.append(indices[opt['mb_size']*i:opt['mb_size']*(i+1)])
	return mb_list


def train(inputs, outputs, optim_step, opt):
	"""Training loop"""
	x, labels, t_params, f_params, lr = inputs
	loss, acc, y, yr = outputs
	
	data = load_data()
	n_data = data['X']['train'].shape[0]
	with tf.Session() as sess:
		init = tf.global_variables_initializer()
		feed_dict = {x: data['X']['train'][:opt['mb_size'],...],
						 t_params: np.zeros((opt['mb_size'],6))}
		sess.run(init, feed_dict=feed_dict)
		
		for epoch in xrange(opt['n_epochs']):
			loss_total = 0.
			acc_total = 0.
			mb_list = random_sampler(n_data, opt)
			current_lr = opt['lr']*np.power(0.1, epoch/opt['lr_interval'])
			for i, mb in enumerate(mb_list):
				tp, fp = el.random_transform(mb.shape[0], (28,28))
				ops = [loss, acc, optim_step]
				feed_dict = {x: data['X']['train'][mb,...],
								 labels: data['Y']['train'][mb,...],
								 t_params: tp,
								 f_params: fp,
								 lr: current_lr}
				l, c, __ = sess.run(ops, feed_dict=feed_dict)
				loss_total += l
				acc_total += c
				sys.stdout.write('{:03d}%\r'.format(int((100.*i)/len(mb_list))))
				sys.stdout.flush()
			loss_total = loss_total / (i+1.)
			acc_total = acc_total / (i+1.)
		
			vacc_total = 0.
			mb_list = random_sampler(data['Y']['valid'].shape[0], opt, random=False)
			for i, mb in enumerate(mb_list):
				feed_dict = {x: data['X']['valid'][mb,...],
								 labels: data['Y']['valid'][mb,...]}
				vc = sess.run(acc, feed_dict=feed_dict)
				vacc_total += vc
			vacc_total = vacc_total / (i+1.)
			
			print('[{:04d}]: Loss: {:04f}, Train Acc.: {:04f}, Valid Acc.: {:04f}' \
					.format(epoch, loss_total, acc_total, vacc_total))
	
		tacc_total = 0.
		mb_list = random_sampler(data['Y']['test'].shape[0], opt, random=False)
		for i, mb in enumerate(mb_list):
			feed_dict = {x: data['X']['test'][mb,...],
							 labels: data['Y']['test'][mb,...]}
			tc = sess.run(acc, feed_dict=feed_dict)
			tacc_total += tc
		tacc_total = tacc_total / (i+1.)
		
		print('Test Acc.: {:04f}'.format(tacc_total))
	return tacc_total

	
def main(opt):
	"""Main loop"""
	
	tf.reset_default_graph()
	opt['N'] = 28
	opt['mb_size'] = 128
	opt['n_channels'] = 10
	opt['n_epochs'] = 100
	opt['lr'] = 1e-2
	opt['lr_interval'] = 33
	#opt['equivariant_weight'] = 1e-3
	
	# Define variables
	x = tf.placeholder(tf.float32, [opt['mb_size'],opt['N'],opt['N'],1], name='x')
	labels = tf.placeholder(tf.float32, [opt['mb_size'],10], name='labels')
	t_params = tf.placeholder(tf.float32, [opt['mb_size'],6], name='t_params')
	f_params = tf.placeholder(tf.float32, [opt['mb_size'],2,2], name='f_params')
	
	lr = tf.placeholder(tf.float32, [], name='lr')
	logits, y, yr = models.siamese_model(x, t_params, f_params, opt)

	# Build loss and metrics
	equi_loss = tf.reduce_mean(tf.square(y - yr))
	classification_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=labels))
	loss = classification_loss + opt['equivariant_weight']*equi_loss
	
	acc = tf.reduce_mean(tf.cast(tf.equal(tf.argmax(logits, axis=1), tf.argmax(labels, axis=1)), tf.float32))
	
	# Build optimizer
	optim = tf.train.MomentumOptimizer(lr, 0.9, use_nesterov=True)
	optim_step = optim.minimize(loss)
	
	inputs = [x, labels, t_params, f_params, lr]
	outputs = [loss, acc, y, yr]
	
	# Train
	return train(inputs, outputs, optim_step, opt)


if __name__ == '__main__':
	opt = {}
	main(opt)
