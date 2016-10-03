Notes by Neeraj :

The code provides 4 different REST APIS to query nearest neighbors for a given
city provided by an identifier. 

The data taken for this project is based from:
http://download.geonames.org/export/dump/cities1000.zip

I'm using flask web framework, and mLab for hosting my mongoDB. 
All data is already added to the database
DB details are int the file server.py

API's:
---------------

GET /cities?count=20
Return all cities - 20 records will be returned

GET /cities?Name=Seattle
Return all possible cities starting with Seattle - 10 records(Default) will be returned

GET /cities?Name=Victoria&count=4
Return all possible cities starting with Victoria - MAX 4 records will be returned

GET /city/10
Return city with id = 10

GET /neighbors/143804?k=20&local=true
Return 20 closest neighbors to city ID = 143804. All of the returned cities are
within the same country 

GET /neighbors/143804?k=20&local=false
Return 20 closest neighbors to city ID = 143804. All of the returned cities
could be in different countries than 143804

GET /neighbors/143804
Return 10 closest neighbors(Default) to city ID = 143804. All of the returned cities
could be in different countries than 143804 ( local is set to false for default)


Approach 1: Bucketize and Min Heap
----------------------------------

The idea is to bucketize each latitude on it's own, and round each city in the
database to it's nearest latitude. As a result, there would be a search set per
latitude. 

When we need to find all closest cities to a target location, we
round it to it's nearest latitude and start with that search bucket. We expand
by going latitude+1 and latitude-1 until we are able to satisfy k(the number of
neighbors to return)

After this, we measure geodistances between the target coordinates(using
haversine formula), and all the
cities coordinates in the searchSet, and add that to a minHeap. We then fetch
the k smallest distances to get the answer. 

Approach 2: KD-Trees
----------------------------------

This approach didn't work for me, but I'm still detailing it, since I did spend
time on it. 

I tried to convert polar coordinates to cartesian coordinates for each city in
the database, and then add that do a KD tree. A KD tree splits per dimension,
and I can query to find the closest elements to a certain target. 

This doesn't give me accurate results - and I feel it might be the function I'm
using to do the conversion from polar to cartesian. 


How to run
-----------------------------------

Need flask, numpy, scipy, pymongo
 > python server.py

http://127.0.0.1:5000/cities?Name=Victoria&count=4
http://127.0.0.1:5000/neighbors/143804?k=20&local=true
