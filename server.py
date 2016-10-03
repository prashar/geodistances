#!/usr/bin/env python

import math
import os
import numpy as np
import scipy as sp
from scipy import spatial
import zipfile
import logging
import pickle 
import heapq
from urllib import urlretrieve
from flask import Flask, jsonify, request, abort
from flask_pymongo import PyMongo

# FlaskDatabase configuration settings
app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'cities'
app.config['MONGO_URI'] = 'mongodb://primer:passw0rd@ds021326.mlab.com:21326/cities'
CollectionName = 'citydb'
mongo = PyMongo(app)

# Global settings for file API
DownloadUrl = "http://download.geonames.org/export/dump/cities1000.zip"
HomeDir = "/Volumes/Data/code/"
ZipFileName = "cities1000.zip"
CityFileName = "cities1000.txt"
CityDataFileName = "cities.txt" 
EarthRadius = 6371000.0
CityIdxToQuery = 143837
NumNearestNeighbors = 10
DefaultCitiesToDisplay = 10
TotalCities = 146654

#============== <Rest Apis> ==================

""" Get number of cities from the database(based on request params or Default   """
""" /cities?name=Seattle                                                        """
""" /cities                                                                     """
""" /cities?name=Victoria&count=4                                               """
@app.route('/cities', methods=['GET'])
def GetDefaultCities():
    name = request.args.get('name',default=None,type=str)
    count = request.args.get('count',default=DefaultCitiesToDisplay,type=int)
    if name is None:
        output = GetCities(count)
    else:
        output = GetCityByName(count,name)
    return jsonify({'result':output})

""" Get the city matching provided ID   """
""" If ID not valid, return 404         """
""" /city/10                            """
@app.route('/city/<int:id>', methods=['GET'])
def GetCityByID(id):
    output = GetCity(id) 
    if(len(output) == 0):
        abort(404)
    return jsonify({'result':output}) ; 

""" Get the nearest k neighbors to the provided CityID  """
""" If ID not valid, return 404                         """
""" Usage:                                              """
""" /neigbors/10?k=5&local=false                        """
@app.route('/neighbors/<int:id>',methods=['GET'])
def GetNeighbors(id):
    k = request.args.get('k',default=NumNearestNeighbors,type=int)
    local = request.args.get('local',default=False,type=bool)
    if local is True:
        targetCity = GetCity(id)
        if(len(targetCity) == 0):
            abort(404)
        cities = GetLocalCities(TotalCities,targetCity['country code'])
    else:
        cities = GetCities(TotalCities)
        targetCity = cities[id]
    model = Bucketizer(cities)
    closestCities = model.FindNearestNeighbors(targetCity,k)
    output = []
    for city in closestCities:
        output.append(city)
    return jsonify({'result':output}) ; 

""" Private Helper Stubs for REST APIS """
def PrepareData(data):
    return {'id':data['id'],'geonameid':data['geonameid'],'name':data['name'],
            'alternatenames':data['alternatenames'],'latitude':data['latitude'],
            'longitude':data['longitude'],'country code':data['country code']}

def GetCities(count):
  with app.app_context():
    cityDB = mongo.db.citydb
    output = []
    for city in cityDB.find().limit(count):
        output.append(PrepareData(city))
    return output

def GetCity(id):
  with app.app_context():
    cityDB = mongo.db.citydb
    city = cityDB.find_one({'id': id})
    if city:
        return(PrepareData(city))
    return {}

def GetLocalCities(count,code):
  with app.app_context():
    cityDB = mongo.db.citydb
    output = []
    for city in cityDB.find({'country code':code}).limit(count):
        output.append(PrepareData(city))
    return output

def GetCityByName(count,name):
  with app.app_context():
    cityDB = mongo.db.citydb
    output = []
    for city in cityDB.find({'name':{'$regex':name}}).limit(count):
        output.append(PrepareData(city))
    return output
    
#==============<Download Data> ================

def DownloadAndExtractZipFile():
    zipPath = os.path.join(HomeDir,ZipFileName)
    if not os.path.exists(zipPath):
        urlretrieve(url,zipPath)
        with zipfile.ZipFile(zipPath,"r") as z:
            z.extractall(HomeDir)

""" Do a batch call to the mLab database I created """ 
def WriteToDB(cityList):
  with app.app_context():
    cityDb = mongo.db.citydb
    if not CollectionName in mongo.db.collection_names():
        cityDb.insert(cityList)
        print "Added all cities!"
    else:
      print "DB exists already!" 

def ExtractRelevantInformation():
    cityFileNameFullPath = os.path.join(HomeDir,CityFileName)
    db = []
    if os.path.exists(cityFileNameFullPath):
        cityDataFileNameFullPath = os.path.join(HomeDir,CityDataFileName) 
        if not os.path.exists(cityDataFileNameFullPath):
            with open(cityFileNameFullPath,'rb') as f:
                lines = f.readlines() ;
            for i,line in enumerate(lines):
                l = line.strip().split('\t')
                db.append({'id': i, 'name': l[2],
                    'latitude':float(l[4]),'longitude': float(l[5]),
                    'cartesian':PolarToCartesian(float(l[4]),float(l[5])),
                    'geonameid':int(l[0]),'country code':l[8],'alternatenames':l[3]})
            with open(cityDataFileNameFullPath, 'wb') as f:
                pickle.dump(db,f)
        else:
            with open(cityDataFileNameFullPath, 'rb') as f:
                db = pickle.load(f) 
    return db ; 

#==============<KDTree Approach>================

def CreateKDTreeForXCities(db):
    points = [] ; 
    print "%d records found !" % len(db)
    for i in xrange(len(db)):
        points.append(db[i]['cartesian'])
    result = np.array(points)
    tree = spatial.KDTree(result)
    return tree ; 

def queryTree(tree,numNeighbors,id,db):
    return tree.query(x=db[id]['cartesian'],k=numNeighbors)

def ParseResult(db, cityIdx, k, distances, indices):
    targetCityName = db[cityIdx]['name'] ; 
    targetCityGeoCoords = [db[cityIdx]['latitude'],db[cityIdx]['longitude']]
    print "City Queried: %s, Lat,Long: (%f,%f): " % (targetCityName,
            targetCityGeoCoords[0],targetCityGeoCoords[1])
    print "Closest cities to %s are --- " % targetCityName
    i = 0 
    while(i < len(distances)):
        cityName = db[indices[i]]['name'] ; 
        cityGeoCoords = [db[indices[i]]['latitude'],db[indices[i]]['longitude']]
        print "City %s, Lat,Long: (%f,%f), GeoDistance: %f, EuclideanDistance: %f" % (cityName,
                cityGeoCoords[0],cityGeoCoords[1],
                DistanceBetweenGeoCoordinates(targetCityGeoCoords,cityGeoCoords),distances[i])
        i+=1

def PolarToCartesian(latitude,longitude):
    x = EarthRadius * math.cos(latitude) * math.cos(longitude)
    y = EarthRadius * math.cos(latitude) * math.sin(longitude)
    z = EarthRadius * math.sin(latitude)
    return [x,y,z]

#==============<Bucketize & MinHeap approach>================

def FindNearestToTarget(searchSet, target, k):
    targetCityGeoCoords = [target['latitude'],target['longitude']] 
    for city in searchSet:
        cityGeoCoords = [city['latitude'],city['longitude']]
        dist = DistanceBetweenGeoCoordinates(cityGeoCoords,targetCityGeoCoords)
        city['distance'] = dist
    closestCities = heapq.nsmallest(k+1, searchSet, key=lambda s: s['distance'])
    closestCities.pop(0)
    return closestCities

def DistanceBetweenGeoCoordinates(geoCoordA, geoCoordB):
    latA, lonA = geoCoordA[0], geoCoordA[1]
    latB, lonB = geoCoordB[0], geoCoordB[1]
    phiA = math.radians(latA)
    phiB = math.radians(latB)
    delta_phi = math.radians(latB-latA)
    delta_delta = math.radians(lonB-lonA)

    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
            math.cos(phiA) * math.cos(phiB) * math.sin(delta_delta/2) * math.sin(delta_delta/2) 
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = EarthRadius * c 
    return d 

class Bucketizer(object):
    def __init__(self,data):
        self.buckets = {}

        for lat in range(-90,91):
            self.buckets[lat] = []
        
        for row in data:
            lat = int(round(row['latitude']))
            self.buckets[lat].append(row)
    
    def FindNearestNeighbors(self, target, k):
        lat = int(round(target['latitude']))
        searchSet = self.buckets[lat]
        for i in range(1,182):
            if(lat - i >= -90):
                searchSet += self.buckets[lat - i]
            if(lat + i <= 90):
                searchSet += self.buckets[lat + i]
            if(len(searchSet) > 0):
                break
        return FindNearestToTarget(searchSet,target,k)

if __name__ == '__main__':
    DownloadAndExtractZipFile() 
    data = ExtractRelevantInformation()
    WriteToDB(data)
    app.run(debug=True)

