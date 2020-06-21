from __future__ import division
import time
import torch 
import torch.nn as nn
import cv2 
from util import write_results, load_classes
from darknet import Darknet
from preprocess import inp_to_image
import argparse
import cloudinary
import cloudinary.uploader
import datetime
import random
import requests


cloudinary.config( 
  cloud_name = "dfl1tke7p", 
  api_key = "429114478873919", 
  api_secret = "yp6A6ArPMghU4hNsl_DciDmnPsA" 
)
clase_actual=-1 #iniciamos con una clase inexistente
ult_tiempo = time.time()

def prep_image(img, inp_dim):
    """
    Prepare image for inputting to the neural network. 
    Returns a Variable 
    """

    orig_im = img
    dim = orig_im.shape[1], orig_im.shape[0]
    img = cv2.resize(orig_im, (inp_dim, inp_dim))
    img_ = img[:,:,::-1].transpose((2,0,1)).copy()
    img_ = torch.from_numpy(img_).float().div(255.0).unsqueeze(0)
    return img_, orig_im, dim

def write(x, img):
    cubrebocas = False;
    global clase_actual
    global ult_tiempo
    c1 = tuple(x[1:3].int())
    c2 = tuple(x[3:5].int())
    cls = int(x[-1])

    suma = torch.sum(x)#Evitamos falsas predicciones

    if cls>2 or cls<0 or suma<1000:#evitamos que falle el programa
        clase_actual=-1#reiniciamos las clases
        return img
    #------Apartado para mostrar la imagen-------------
    label = "{0}".format(classes[cls])
    if label == 'mask':
        cubrebocas=True
        color = (100, 221, 23)
    else:
        color = (0,0,213)
    cv2.rectangle(img, c1, c2,color, 3)
    t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 1 , 1)[0]
    c2 = c1[0] + t_size[0] + 3, c1[1] + t_size[1] + 4
    cv2.rectangle(img, c1, c2,color, -1)
    cv2.putText(img, label, (c1[0], c1[1] + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225,255,255], 1);
    #-------Apartado para enviar la imagen al servidor
    if( (cls != clase_actual) and (time.time()>ult_tiempo+15)):

        print(time.time()-ult_tiempo)
        cv2.imwrite('captura.jpg',img)
        #res=cloudinary.uploader.upload('captura.jpg',folder='covid_mask/')
        #print('url: ',res['url'])
        #---mandamos info al servidor loopback
        datetime_object = datetime.datetime.now()
        string_fecha = str(datetime_object).split('.')[0]

        nombres = ['Manuel','Alejandro','Ilse','Diana','Ovaldo']
        nCuentas = [74017401,8483946,5816502,8571536,1857254]

        datajson={#json para loopback
            "horaEntrada": string_fecha,
            "nCuenta": random.choice(nCuentas),
            "nombre": random.choice(nombres),
            "cubrebocas": cubrebocas,
            "tipoPersona": "Estudiante",
            "linkImg": res['url']
        }

        a=requests.post('http://localhost:3000/ingreso-infos',json=datajson)

        clase_actual=cls#solo hace el proceso en los cambios de clase
        ult_tiempo=time.time()#solo hace el proceso cada 15s como minimo
    return img

def arg_parse():
    """
    Parse arguements to the detect module
    """
    parser = argparse.ArgumentParser(description='YOLO v3 Cam Demo')
    parser.add_argument("--confidence", dest = "confidence", help = "Object Confidence to filter predictions", default = 0.25)
    parser.add_argument("--nms_thresh", dest = "nms_thresh", help = "NMS Threshhold", default = 0.4)
    parser.add_argument("--reso", dest = 'reso', help = 
                        "Input resolution of the network. Increase to increase accuracy. Decrease to increase speed",
                        default = "416", type = str)
    return parser.parse_args()



if __name__ == '__main__':

    cfgfile = "cfg/yolov3-tiny-obj.cfg"
    weightsfile = "yolov3-tiny-obj_final.weights"
    num_classes = 2

    args = arg_parse()
    confidence = float(args.confidence)
    nms_thesh = float(args.nms_thresh)
    start = 0
    CUDA = torch.cuda.is_available()
    
    bbox_attrs = 5 + num_classes
    
    model = Darknet(cfgfile)
    model.load_weights(weightsfile)
    
    model.net_info["height"] = args.reso
    inp_dim = int(model.net_info["height"])#default 416
    
    assert inp_dim % 32 == 0 #verfica si es multiplo de 32
    assert inp_dim > 32 #y mayor a 32

    if CUDA:
        model.cuda()
            
    model.eval()
    
    videofile = 'video.avi'
    
    cap = cv2.VideoCapture(0)
    
    assert cap.isOpened(), 'Cannot capture source'
    
    frames = 0

    while cap.isOpened():#mientas haya señal de la camara 
        ret, frame = cap.read()
        if ret:

            
            img, orig_im, dim = prep_image(frame, inp_dim)
                        
            
            if CUDA:
                im_dim = im_dim.cuda()
                img = img.cuda()
            
            
            output = model(img, CUDA)
            output = write_results(output, confidence, num_classes, nms = True, nms_conf = nms_thesh)
        
            output[:,1:5] = torch.clamp(output[:,1:5], 0.0, float(inp_dim))/inp_dim
            
            output[:,[1,3]] *= frame.shape[1]
            output[:,[2,4]] *= frame.shape[0]

            
            classes = load_classes('data/coco.names')
            

            list(map(lambda x: write(x, orig_im),output))
            
            cv2.imshow("frame", orig_im)
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break
            frames += 1

        else:
            break
    

    
    

