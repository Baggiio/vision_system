from distutils.log import error
from importlib.util import module_for_loader
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image, ImageFile
import cv2
import extcolors
import os
from colormap import rgb2hex
from tensorflow.keras.preprocessing.image import load_img
from tensorflow.keras.preprocessing.image import img_to_array
from u2net_test import mask
import glob
import json
from mask_detect import ifmask
from height_estimate import height_estimate


def creating_mask():
    pf = glob.glob('/home/robofei/catkin_hera/src/3rdParty/vision_system/feature-extraction/images/*')
    img_path = pf[0]
    output = mask(img_path)
    output = load_img(output)
    RESCALE = 255
    out_img = img_to_array(output) / RESCALE
    THRESHOLD = 0.2
    out_img[out_img > THRESHOLD] = 1
    out_img[out_img <= THRESHOLD] = 0
    shape = out_img.shape
    print("Shape: ", shape)
    a_layer_init = np.ones(shape=(shape[0], shape[1], 1))
    mul_layer = np.expand_dims(out_img[:, :, 0], axis=2)
    a_layer = mul_layer * a_layer_init
    rgba_out = np.append(out_img, a_layer, axis=2)

    
    original_image_path = img_path
    original_image = load_img(original_image_path)
    inp_img = img_to_array(original_image)
    inp_img /= RESCALE
    # since the output image is rgba, convert this also to rgba, but with no transparency
    a_layer = np.ones(shape=(shape[0], shape[1], 1))
    print("Shape 1", a_layer.shape)
    print("Shape 2", inp_img.shape)
    rgba_inp = np.append(inp_img, a_layer, axis=2)
    print("Shape 3", rgba_inp.shape)
    print("Shape 4", rgba_out.shape)
    # simply multiply the 2 rgba images to remove the backgound
    rem_back = (rgba_inp * rgba_out)
    rem_back_scaled = Image.fromarray((rem_back * RESCALE).astype('uint8'), 'RGBA')
    # save the resulting image to colab

    rem_back_scaled.save('results/removed_background.png')

    out_layer = out_img[:,:,1]
    y_starts = [np.where(out_layer.T[i]==1)[0][0] if len(np.where(out_layer.T[i]==1)[0])!=0 else out_layer.T.shape[0]+1 for i in range(out_layer.T.shape[0])]
    
    global starty
    starty = min(y_starts)

def pose_points(path_image):
    null = 'null'
    
    BODY_PARTS = {"Nose": 0, "Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4,
                  "LShoulder": 5, "LElbow": 6, "LWrist": 7, "RHip": 8, "RKnee": 9,
                  "RAnkle": 10, "LHip": 11, "LKnee": 12, "LAnkle": 13, "REye": 14,
                  "LEye": 15, "REar": 16, "LEar": 17, "Background": 18}

    POSE_PAIRS = [["Neck", "RShoulder"], ["Neck", "LShoulder"], ["RShoulder", "RElbow"],
                  ["RElbow", "RWrist"], ["LShoulder", "LElbow"], ["LElbow", "LWrist"],
                  ["Neck", "RHip"], ["RHip", "RKnee"], ["RKnee", "RAnkle"], ["Neck", "LHip"],
                  ["LHip", "LKnee"], ["LKnee", "LAnkle"], ["Neck", "Nose"], ["Nose", "REye"],
                  ["REye", "REar"], ["Nose", "LEye"], ["LEye", "LEar"]]
    inWidth = 480
    inHeight = 640
    net = cv2.dnn.readNetFromTensorflow("/home/robofei/catkin_hera/src/3rdParty/vision_system/feature-extraction/graph_opt.pb")
    cap = cv2.imread(path_image)
    #cap = cv2.resize(aux, (720, 1280))

    
    frame = cap
    print(cap)

    frameWidth = frame.shape[1]
    frameHeight = frame.shape[0]

    net.setInput(
        cv2.dnn.blobFromImage(frame, 1.0, (inWidth, inHeight), (127.5, 127.5, 127.5), swapRB=True, crop=False))
    out = net.forward()
    out = out[:, :19, :, :]  # MobileNet output [1, 57, -1, -1], we only need the first 19 elements

    assert (len(BODY_PARTS) == out.shape[1])

    points = []
    for i in range(len(BODY_PARTS)):
        # Slice heatmap of corresponging body's part.
        heatMap = out[0, i, :, :]

        # Originally, we try to find all the local maximums. To simplify a sample
        # we just find a global one. However only a single pose at the same time
        # could be detected this way.
        _, conf, _, point = cv2.minMaxLoc(heatMap)
        x = (frameWidth * point[0]) / out.shape[3]
        y = (frameHeight * point[1]) / out.shape[2]
        # Add a point if it's confidence is higher than threshold.
        points.append((int(x), int(y)) if conf > 0.2 else None)

    for pair in POSE_PAIRS:
        partFrom = pair[0]
        partTo = pair[1]
        assert (partFrom in BODY_PARTS)
        assert (partTo in BODY_PARTS)

        idFrom = BODY_PARTS[partFrom]
        idTo = BODY_PARTS[partTo]

        if points[idFrom] and points[idTo]:
            cv2.line(frame, points[idFrom], points[idTo], (0, 255, 0), 3)
            cv2.ellipse(frame, points[idFrom], (3, 3), 0, 0, 360, (0, 0, 255), cv2.FILLED)
            cv2.ellipse(frame, points[idTo], (3, 3), 0, 0, 360, (0, 0, 255), cv2.FILLED)

        t, _ = net.getPerfProfile()
        freq = cv2.getTickFrequency() / 1000
        lx = cv2.putText(frame, '%.2fms' % (t / freq), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0))
        cv2.imwrite('results/pose_points.png', lx)
        with open('points.json', 'w') as f:
            json.dump(points, f)

        break
        
    with open('points.json', 'r') as f:
        point = json.load(f)


    neck = point[1][1]
    cint = point[8][1] + 25
    if point[12][1] != null:
        knee = point[12][1]
        print(knee)
    elif point[9][1] != null:
        knee = point[9][1]
        print(knee)
    else:
        knee = null
        print(knee)

    creating_mask()
       
    way = glob.glob('images/*')
    for py_file in way:
        try:
            os.remove(py_file)
        except OSError as e:
            print(f"Error:{ e.strerror}")
            
    modelo = cv2.imread('results/removed_background.png')

    for x in range(3):
        if x == 0:
            foto = modelo[neck - 25:cint, 0:]
            cv2.imwrite('images/torso.png', foto)  
        elif x == 1:
            if knee != null:
                print("AQUI", knee)
                print("CINT:", cint)
                foto = modelo[cint - 25:knee, 0:]
                print(type(foto))
                cv2.imwrite('images/pernas.png', foto)
            else: 
                foto = modelo[cint - 25:, 0:]
                cv2.imwrite('images/pernas.png', foto)
        else:
            foto = modelo[:neck - 10]
            cv2.imwrite('images/cabeca.png', foto)    
    print("Saved points!!")



def color(xxxxx):
    ImageFile.LOAD_TRUNCATED_IMAGES = True  # Permitir que imagens corrompidas sejam usadas
    segm_image = xxxxx  # Caminho da imagem
    # Mostrar imagem
    plt.figure(figsize=(9, 9))
    img = plt.imread(segm_image)
    plt.imshow(img)
    plt.axis('off')

    colors_x = extcolors.extract_from_path(segm_image, tolerance=12, limit=12)

    rgb = (colors_x[0][0][0])

    if rgb == (0, 0, 0):
        rgb = (colors_x[0][1][0])
        print(rgb)
    if rgb == (255, 255, 255):
        print('White')
        return 'White'
    if rgb < (45, 45, 45):
        print('Black')
        return 'Black'
    elif rgb[0] == rgb[1] and rgb[1] == rgb[2] and rgb[0] == rgb[2]:
        print('Grey')
        return 'Grey'

    elif rgb[0] > rgb[1] and rgb[0] > rgb[2]:
        if rgb[0] > 209 and rgb[1] > 179 and rgb[2] > 134 and rgb != (255, 192, 203):
            print('Beige')
            return 'Beige'

        elif (rgb == (184, 134, 11) or rgb == (189, 83, 107) or rgb == (139, 69, 19) or rgb == (160, 82, 45) or rgb == (
        188, 143, 143)) or rgb[0] > 204 and rgb[1] > 104 and rgb[2] < 144:
            print('Brown')
            return 'Brown'

        elif rgb[0] > 204 and rgb[1] < 193 and rgb[2] > 91:
            print('Pink')
            return 'Pink'

        elif rgb == (255, 140, 0) or rgb == (255, 165, 0):
            print('Orange')
            return 'Orange'

        elif rgb == (255, 215, 0):
            print('Gold')
            return 'Gold'
        elif rgb == (189, 83, 107):
            print('Green')
            return 'Green'
        else:
            print('Red')
            return 'Red'

    elif rgb[1] > rgb[0] and rgb[1] > rgb[2] or rgb == (47, 79, 79):
        if rgb == (133, 130, 111) or rgb == (124, 125, 111):
            print('Beige')
            return 'Beige'
        print('green')
        return 'Green'

    elif rgb[2] > rgb[1] and rgb[2] > rgb[0] or rgb == (0, 255, 255) or rgb == (0, 139, 139) or rgb == (0, 128, 128):
        if rgb[0] > 122 and rgb[1] < 113 and rgb[2] > 203 or rgb == (128, 0, 128) or rgb == (75, 0, 130):
            print('Purple')
            return 'Purple'
        else:
            print('Blue')
            return 'Blue'

    elif rgb == (128, 128, 0):
        print('Green')
        return 'Green'
    elif rgb == (255, 255, 0):
        print('Yellow')
        return 'Yellow'
    elif rgb == (255, 0, 255) or rgb == (238, 130, 238) or rgb == (218, 112, 214) or rgb == (221, 160, 221):
        print('Pink')
        return 'Pink'


def features(img_path):

    # Separate the person in three parts and save a photo of each part and takes the path from it
    # body_parts - list of the body_image paths
    pose_points(img_path) 
    
    # Create a mask for the person and remove background
    
    # Create a empty list to save the colors
    body_colors = []

    for parts in glob.glob('images/*'):

        if parts == 'images/cabeca.png':
            ifmask('images/cabeca.png')
        
        print(parts)
        # Get the main color of the image
        output_color = color(parts)
        # Add to the body_colors list
        # First element[0] is the torso color, second[1] is the legs color
        body_colors.append(output_color)
    # Return the list of colors
    print(body_colors)
    print("Pixel topo = ", starty)
    height_estimate(150, starty)
    return body_colors

features('/home/robofei/catkin_hera/src/3rdParty/vision_system/feature-extraction/images/bgg150.jpg')




