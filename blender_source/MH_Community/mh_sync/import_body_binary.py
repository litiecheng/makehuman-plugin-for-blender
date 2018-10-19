#!/usr/bin/python
# -*- coding: utf-8 -*-

bl_info = {
    "name": "Import body from MakeHuman",
    "category": "Mesh",
}

import bpy
import bmesh
import pprint
import struct
import time
import itertools

from .material import *
from .fetch_server_data import FetchServerData

pp = pprint.PrettyPrinter(indent=4)

class ImportBodyBinary():

    def __init__(self):
        print("Import body")
        self.scaleFactor = 0.1

        self.startMillis = int(round(time.time() * 1000))
        self.lastMillis = self.startMillis

        self.scaleMode = str(bpy.context.scene.MhScaleMode)

        if self.scaleMode == "DECIMETER":
            self.scaleFactor = 1.0

        if self.scaleMode == "CENTIMETER":
            self.scaleFactor = 10.0

        self.minimumZ = 10000.0
        FetchServerData('getBodyMeshInfo', self.gotBodyInfo)

    def _profile(self, position="timestamp"):
        currentMillis = int(round(time.time() * 1000))
        print(position + ": " + str(currentMillis - self.startMillis) + " / " + str(currentMillis - self.lastMillis))
        self.lastMillis = currentMillis

    def gotBodyInfo(self, data):
        #print(data)
        self.bodyInfo = data

        self.mesh = bpy.data.meshes.new("HumanBodyMesh")
        self.obj = bpy.data.objects.new("HumanBody", self.mesh)

        scene = bpy.context.scene
        scene.objects.link(self.obj)
        scene.objects.active = self.obj
        self.obj.select = True

        self.mesh = bpy.context.object.data
        self.bm = bmesh.new()

        FetchServerData('getBodyVerticesBinary',self.gotVerticesData,True)

    def gotVerticesData(self, data):
        self._profile()
        print(len(data))
        print(len(data) / 4 / 3)
        print(self.bodyInfo["numVertices"])

        self.vertCache = []

        iMax = int(len(data) / 4 / 3)
        assert(iMax == int(self.bodyInfo["numVertices"]))

        i = 0
        while i < iMax:
            sliceStart = i * 4 * 3 # 4-byte floats, three vertices

            xbytes = data[sliceStart:sliceStart + 4]
            ybytes = data[sliceStart + 4:sliceStart + 4 + 4]
            zbytes = data[sliceStart + 4 + 4:sliceStart + 4 + 4 +4]

            x = struct.unpack("f", bytes(xbytes))[0] * self.scaleFactor
            y = struct.unpack("f", bytes(ybytes))[0] * self.scaleFactor
            z = struct.unpack("f", bytes(zbytes))[0] * self.scaleFactor

            if z < self.minimumZ:
                self.minimumZ = z

            # Coordinate order from MH is XZY
            vert = self.bm.verts.new( (x, z, y) )
            vert.index = i

            self.vertCache.append(vert)

            i = i + 1

        FetchServerData('getBodyFacesBinary',self.gotFacesData,True)

    def gotFacesData(self, data):
        self._profile()
        print(len(data))
        print(len(data) / 4 / 4)
        print(self.bodyInfo)

        self.faceCache = []
        self.faceVertIndexes=[]

        iMax = int(len(data) / 4 / 4)
        assert (iMax == int(self.bodyInfo["numFaces"]))

        i = 0
        while i < iMax:
            sliceStart = i * 4 * 4  # 4-byte unsigned ints, four verts per face

            stride = 0;
            verts = [None, None, None, None]
            vertIdxs = [None, None, None, None]

            while stride < 4:
                sliceStart = i * 4 * 4  # 4-byte floats, three vertices
                vertbytes = data[sliceStart + stride * 4:sliceStart + stride * 4 + 4]
                vert = self.vertCache[int(struct.unpack("I", bytes(vertbytes))[0])]
                verts[stride] = vert
                vertIdxs[stride] = vert.index
                stride = stride + 1
            face = self.bm.faces.new(verts)
            face.index = i
            face.smooth = True
            self.faceCache.append(face)
            self.faceVertIndexes.append(vertIdxs)
            i = i + 1

        self.afterMeshData()

    def handleHelpers(self):

        all_joint_verts = []
        all_helper_verts = []

        for fg in self.bodyInfo["faceGroups"]:
            name = fg["name"]
            self._profile(name)
            first = fg["first"]
            last = fg["last"]

            verts = []
            faceSubSet = self.faceVertIndexes[first:last]

            verts = list(set(itertools.chain.from_iterable(faceSubSet)))

            self._profile("after verts")

            if len(verts) > 0:
                if name.startswith("joint-"):
                    all_joint_verts.extend(verts)
                if name.startswith("helper-"):
                    all_helper_verts.extend(verts)
                if self.helpers == "MASK":
                    vgroup = self.obj.vertex_groups.new(name=name)
                    vgroup.add(verts, 1.0, 'ADD')

        if self.helpers == "DELETE":
            if len(all_joint_verts) > 0:
                # TODO: delete vertices
                pass
            if len(all_helper_verts) > 0:
                # TODO: delete vertices
                pass

        if self.helpers == "MASK":
            mask = self.obj.modifiers.new("Mask", 'MASK')
            mask.vertex_group = "body"
            mask.show_in_editmode = True
            mask.show_on_cage = True

    def afterMeshData(self):

        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)

        self.bm.to_mesh(self.mesh)
        self.bm.free()

        self.helpers = str(bpy.context.scene.handle_helper)

        if self.helpers != "NOTHING":
            self.handleHelpers()

        del self.vertCache
        del self.faceCache

        FetchServerData('getBodyMaterialInfo',self.gotBodyMaterialInfo)

    def gotBodyMaterialInfo(self, data):
        print(data)
        mat = createMHMaterial("testa", data)
        self.obj.data.materials.append(mat)






