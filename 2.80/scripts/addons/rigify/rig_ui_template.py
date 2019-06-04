#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

# <pep8 compliant>

UI_IMPORTS = [
    'import bpy',
    'from bpy.props import StringProperty',
    'import math',
    'from math import pi',
    'from mathutils import Euler, Matrix, Quaternion, Vector',
]

UI_BASE_UTILITIES = '''
rig_id = "%s"


############################
## Math utility functions ##
############################

def perpendicular_vector(v):
    """ Returns a vector that is perpendicular to the one given.
        The returned vector is _not_ guaranteed to be normalized.
    """
    # Create a vector that is not aligned with v.
    # It doesn't matter what vector.  Just any vector
    # that's guaranteed to not be pointing in the same
    # direction.
    if abs(v[0]) < abs(v[1]):
        tv = Vector((1,0,0))
    else:
        tv = Vector((0,1,0))

    # Use cross prouct to generate a vector perpendicular to
    # both tv and (more importantly) v.
    return v.cross(tv)


def rotation_difference(mat1, mat2):
    """ Returns the shortest-path rotational difference between two
        matrices.
    """
    q1 = mat1.to_quaternion()
    q2 = mat2.to_quaternion()
    angle = math.acos(min(1,max(-1,q1.dot(q2)))) * 2
    if angle > pi:
        angle = -angle + (2*pi)
    return angle

def tail_distance(angle,bone_ik,bone_fk):
    """ Returns the distance between the tails of two bones
        after rotating bone_ik in AXIS_ANGLE mode.
    """
    rot_mod=bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'
    bone_ik.rotation_axis_angle[0] = angle
    bpy.context.view_layer.update()

    dv = (bone_fk.tail - bone_ik.tail).length

    bone_ik.rotation_mode = rot_mod
    return dv

def find_min_range(bone_ik,bone_fk,f=tail_distance,delta=pi/8):
    """ finds the range where lies the minimum of function f applied on bone_ik and bone_fk
        at a certain angle.
    """
    rot_mod=bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'

    start_angle = bone_ik.rotation_axis_angle[0]
    angle = start_angle
    while (angle > (start_angle - 2*pi)) and (angle < (start_angle + 2*pi)):
        l_dist = f(angle-delta,bone_ik,bone_fk)
        c_dist = f(angle,bone_ik,bone_fk)
        r_dist = f(angle+delta,bone_ik,bone_fk)
        if min((l_dist,c_dist,r_dist)) == c_dist:
            bone_ik.rotation_mode = rot_mod
            return (angle-delta,angle+delta)
        else:
            angle=angle+delta

def ternarySearch(f, left, right, bone_ik, bone_fk, absolutePrecision):
    """
    Find minimum of unimodal function f() within [left, right]
    To find the maximum, revert the if/else statement or revert the comparison.
    """
    while True:
        #left and right are the current bounds; the maximum is between them
        if abs(right - left) < absolutePrecision:
            return (left + right)/2

        leftThird = left + (right - left)/3
        rightThird = right - (right - left)/3

        if f(leftThird, bone_ik, bone_fk) > f(rightThird, bone_ik, bone_fk):
            left = leftThird
        else:
            right = rightThird

#########################################
## "Visual Transform" helper functions ##
#########################################

def get_pose_matrix_in_other_space(mat, pose_bone):
    """ Returns the transform matrix relative to pose_bone's current
        transform space.  In other words, presuming that mat is in
        armature space, slapping the returned matrix onto pose_bone
        should give it the armature-space transforms of mat.
        TODO: try to handle cases with axis-scaled parents better.
    """
    rest = pose_bone.bone.matrix_local.copy()
    rest_inv = rest.inverted()
    if pose_bone.parent:
        par_mat = pose_bone.parent.matrix.copy()
        par_inv = par_mat.inverted()
        par_rest = pose_bone.parent.bone.matrix_local.copy()
    else:
        par_mat = Matrix()
        par_inv = Matrix()
        par_rest = Matrix()

    # Get matrix in bone's current transform space
    smat = rest_inv @ (par_rest @ (par_inv @ mat))

    # Compensate for non-local location
    #if not pose_bone.bone.use_local_location:
    #    loc = smat.to_translation() @ (par_rest.inverted() @ rest).to_quaternion()
    #    smat.translation = loc

    return smat


def get_local_pose_matrix(pose_bone):
    """ Returns the local transform matrix of the given pose bone.
    """
    return get_pose_matrix_in_other_space(pose_bone.matrix, pose_bone)


def set_pose_translation(pose_bone, mat):
    """ Sets the pose bone's translation to the same translation as the given matrix.
        Matrix should be given in bone's local space.
    """
    if pose_bone.bone.use_local_location == True:
        pose_bone.location = mat.to_translation()
    else:
        loc = mat.to_translation()

        rest = pose_bone.bone.matrix_local.copy()
        if pose_bone.bone.parent:
            par_rest = pose_bone.bone.parent.matrix_local.copy()
        else:
            par_rest = Matrix()

        q = (par_rest.inverted() @ rest).to_quaternion()
        pose_bone.location = q @ loc


def set_pose_rotation(pose_bone, mat):
    """ Sets the pose bone's rotation to the same rotation as the given matrix.
        Matrix should be given in bone's local space.
    """
    q = mat.to_quaternion()

    if pose_bone.rotation_mode == 'QUATERNION':
        pose_bone.rotation_quaternion = q
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        pose_bone.rotation_axis_angle[0] = q.angle
        pose_bone.rotation_axis_angle[1] = q.axis[0]
        pose_bone.rotation_axis_angle[2] = q.axis[1]
        pose_bone.rotation_axis_angle[3] = q.axis[2]
    else:
        pose_bone.rotation_euler = q.to_euler(pose_bone.rotation_mode)


def set_pose_scale(pose_bone, mat):
    """ Sets the pose bone's scale to the same scale as the given matrix.
        Matrix should be given in bone's local space.
    """
    pose_bone.scale = mat.to_scale()


def match_pose_translation(pose_bone, target_bone):
    """ Matches pose_bone's visual translation to target_bone's visual
        translation.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    set_pose_translation(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def match_pose_rotation(pose_bone, target_bone):
    """ Matches pose_bone's visual rotation to target_bone's visual
        rotation.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    set_pose_rotation(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')


def match_pose_scale(pose_bone, target_bone):
    """ Matches pose_bone's visual scale to target_bone's visual
        scale.
        This function assumes you are in pose mode on the relevant armature.
    """
    mat = get_pose_matrix_in_other_space(target_bone.matrix, pose_bone)
    set_pose_scale(pose_bone, mat)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')

def correct_rotation(bone_ik, bone_fk):
    """ Corrects the ik rotation in ik2fk snapping functions
    """

    alfarange = find_min_range(bone_ik,bone_fk)
    alfamin = ternarySearch(tail_distance,alfarange[0],alfarange[1],bone_ik,bone_fk,0.1)

    rot_mod = bone_ik.rotation_mode
    if rot_mod != 'AXIS_ANGLE':
        bone_ik.rotation_mode = 'AXIS_ANGLE'
    bone_ik.rotation_axis_angle[0] = alfamin
    bone_ik.rotation_mode = rot_mod

##############################
## IK/FK snapping functions ##
##############################

def match_pole_target(ik_first, ik_last, pole, match_bone, length):
    """ Places an IK chain's pole target to match ik_first's
        transforms to match_bone.  All bones should be given as pose bones.
        You need to be in pose mode on the relevant armature object.
        ik_first: first bone in the IK chain
        ik_last:  last bone in the IK chain
        pole:  pole target bone for the IK chain
        match_bone:  bone to match ik_first to (probably first bone in a matching FK chain)
        length:  distance pole target should be placed from the chain center
    """
    a = ik_first.matrix.to_translation()
    b = ik_last.matrix.to_translation() + ik_last.vector

    # Vector from the head of ik_first to the
    # tip of ik_last
    ikv = b - a

    # Get a vector perpendicular to ikv
    pv = perpendicular_vector(ikv).normalized() * length

    def set_pole(pvi):
        """ Set pole target's position based on a vector
            from the arm center line.
        """
        # Translate pvi into armature space
        ploc = a + (ikv/2) + pvi

        # Set pole target to location
        mat = get_pose_matrix_in_other_space(Matrix.Translation(ploc), pole)
        set_pose_translation(pole, mat)

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')

    set_pole(pv)

    # Get the rotation difference between ik_first and match_bone
    angle = rotation_difference(ik_first.matrix, match_bone.matrix)

    # Try compensating for the rotation difference in both directions
    pv1 = Matrix.Rotation(angle, 4, ikv) @ pv
    set_pole(pv1)
    ang1 = rotation_difference(ik_first.matrix, match_bone.matrix)

    pv2 = Matrix.Rotation(-angle, 4, ikv) @ pv
    set_pole(pv2)
    ang2 = rotation_difference(ik_first.matrix, match_bone.matrix)

    # Do the one with the smaller angle
    if ang1 < ang2:
        set_pole(pv1)

##########
## Misc ##
##########

def parse_bone_names(names_string):
    if names_string[0] == '[' and names_string[-1] == ']':
        return eval(names_string)
    else:
        return names_string

'''

UTILITIES_FUNC_ARM_FKIK = ['''
######################
## IK Arm functions ##
######################

def fk2ik_arm(obj, fk, ik):
    """ Matches the fk bones in an arm rig to the ik bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    uarm  = obj.pose.bones[fk[0]]
    farm  = obj.pose.bones[fk[1]]
    hand  = obj.pose.bones[fk[2]]
    uarmi = obj.pose.bones[ik[0]]
    farmi = obj.pose.bones[ik[1]]
    handi = obj.pose.bones[ik[2]]

    if 'auto_stretch' in handi.keys():
        # This is kept for compatibility with legacy rigify Human
        # Stretch
        if handi['auto_stretch'] == 0.0:
            uarm['stretch_length'] = handi['stretch_length']
        else:
            diff = (uarmi.vector.length + farmi.vector.length) / (uarm.vector.length + farm.vector.length)
            uarm['stretch_length'] *= diff

        # Upper arm position
        match_pose_rotation(uarm, uarmi)
        match_pose_scale(uarm, uarmi)

        # Forearm position
        match_pose_rotation(farm, farmi)
        match_pose_scale(farm, farmi)

        # Hand position
        match_pose_rotation(hand, handi)
        match_pose_scale(hand, handi)
    else:
        # Upper arm position
        match_pose_translation(uarm, uarmi)
        match_pose_rotation(uarm, uarmi)
        match_pose_scale(uarm, uarmi)

        # Forearm position
        #match_pose_translation(hand, handi)
        match_pose_rotation(farm, farmi)
        match_pose_scale(farm, farmi)

        # Hand position
        match_pose_translation(hand, handi)
        match_pose_rotation(hand, handi)
        match_pose_scale(hand, handi)


def ik2fk_arm(obj, fk, ik):
    """ Matches the ik bones in an arm rig to the fk bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    uarm  = obj.pose.bones[fk[0]]
    farm  = obj.pose.bones[fk[1]]
    hand  = obj.pose.bones[fk[2]]
    uarmi = obj.pose.bones[ik[0]]
    farmi = obj.pose.bones[ik[1]]
    handi = obj.pose.bones[ik[2]]

    main_parent = obj.pose.bones[ik[4]]

    if ik[3] != "" and main_parent['pole_vector']:
        pole  = obj.pose.bones[ik[3]]
    else:
        pole = None


    if pole:
        # Stretch
        # handi['stretch_length'] = uarm['stretch_length']

        # Hand position
        match_pose_translation(handi, hand)
        match_pose_rotation(handi, hand)
        match_pose_scale(handi, hand)
        # Pole target position
        match_pole_target(uarmi, farmi, pole, uarm, (uarmi.length + farmi.length))

    else:
        # Hand position
        match_pose_translation(handi, hand)
        match_pose_rotation(handi, hand)
        match_pose_scale(handi, hand)

        # Upper Arm position
        match_pose_translation(uarmi, uarm)
        match_pose_rotation(uarmi, uarm)
        match_pose_scale(uarmi, uarm)
        # Rotation Correction
        correct_rotation(uarmi, uarm)
''']

UTILITIES_FUNC_LEG_FKIK = ['''
######################
## IK Leg functions ##
######################

def fk2ik_leg(obj, fk, ik):
    """ Matches the fk bones in a leg rig to the ik bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    thigh  = obj.pose.bones[fk[0]]
    shin   = obj.pose.bones[fk[1]]
    foot   = obj.pose.bones[fk[2]]
    mfoot  = obj.pose.bones[fk[3]]
    thighi = obj.pose.bones[ik[0]]
    shini  = obj.pose.bones[ik[1]]
    footi  = obj.pose.bones[ik[2]]
    mfooti = obj.pose.bones[ik[3]]

    if 'auto_stretch' in footi.keys():
        # This is kept for compatibility with legacy rigify Human
        # Stretch
        if footi['auto_stretch'] == 0.0:
            thigh['stretch_length'] = footi['stretch_length']
        else:
            diff = (thighi.vector.length + shini.vector.length) / (thigh.vector.length + shin.vector.length)
            thigh['stretch_length'] *= diff

        # Thigh position
        match_pose_rotation(thigh, thighi)
        match_pose_scale(thigh, thighi)

        # Shin position
        match_pose_rotation(shin, shini)
        match_pose_scale(shin, shini)

        # Foot position
        mat = mfoot.bone.matrix_local.inverted() @ foot.bone.matrix_local
        footmat = get_pose_matrix_in_other_space(mfooti.matrix, foot) @ mat
        set_pose_rotation(foot, footmat)
        set_pose_scale(foot, footmat)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')

    else:
        # Thigh position
        match_pose_translation(thigh, thighi)
        match_pose_rotation(thigh, thighi)
        match_pose_scale(thigh, thighi)

        # Shin position
        match_pose_rotation(shin, shini)
        match_pose_scale(shin, shini)

        # Foot position
        mat = mfoot.bone.matrix_local.inverted() @ foot.bone.matrix_local
        footmat = get_pose_matrix_in_other_space(mfooti.matrix, foot) @ mat
        set_pose_rotation(foot, footmat)
        set_pose_scale(foot, footmat)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')


def ik2fk_leg(obj, fk, ik):
    """ Matches the ik bones in a leg rig to the fk bones.
        obj: armature object
        fk:  list of fk bone names
        ik:  list of ik bone names
    """
    thigh    = obj.pose.bones[fk[0]]
    shin     = obj.pose.bones[fk[1]]
    mfoot    = obj.pose.bones[fk[2]]
    if fk[3] != "":
        foot      = obj.pose.bones[fk[3]]
    else:
        foot = None
    thighi   = obj.pose.bones[ik[0]]
    shini    = obj.pose.bones[ik[1]]
    footi    = obj.pose.bones[ik[2]]
    footroll = obj.pose.bones[ik[3]]

    main_parent = obj.pose.bones[ik[6]]

    if ik[4] != "" and main_parent['pole_vector']:
        pole     = obj.pose.bones[ik[4]]
    else:
        pole = None
    mfooti   = obj.pose.bones[ik[5]]

    if (not pole) and (foot):

        # Clear footroll
        set_pose_rotation(footroll, Matrix())

        # Foot position
        mat = mfooti.bone.matrix_local.inverted() @ footi.bone.matrix_local
        footmat = get_pose_matrix_in_other_space(foot.matrix, footi) @ mat
        set_pose_translation(footi, footmat)
        set_pose_rotation(footi, footmat)
        set_pose_scale(footi, footmat)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')

        # Thigh position
        match_pose_translation(thighi, thigh)
        match_pose_rotation(thighi, thigh)
        match_pose_scale(thighi, thigh)

        # Rotation Correction
        correct_rotation(thighi,thigh)

    else:
        # Stretch
        if 'stretch_lenght' in footi.keys() and 'stretch_lenght' in thigh.keys():
            # Kept for compat with legacy rigify Human
            footi['stretch_length'] = thigh['stretch_length']

        # Clear footroll
        set_pose_rotation(footroll, Matrix())

        # Foot position
        mat = mfooti.bone.matrix_local.inverted() @ footi.bone.matrix_local
        footmat = get_pose_matrix_in_other_space(mfoot.matrix, footi) @ mat
        set_pose_translation(footi, footmat)
        set_pose_rotation(footi, footmat)
        set_pose_scale(footi, footmat)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')

        # Pole target position
        match_pole_target(thighi, shini, pole, thigh, (thighi.length + shini.length))
''']

UTILITIES_FUNC_POLE = ['''
################################
## IK Rotation-Pole functions ##
################################

def rotPoleToggle(rig, limb_type, controls, ik_ctrl, fk_ctrl, parent, pole):

    rig_id = rig.data['rig_id']
    leg_fk2ik = eval('bpy.ops.pose.rigify_leg_fk2ik_' + rig_id)
    arm_fk2ik = eval('bpy.ops.pose.rigify_arm_fk2ik_' + rig_id)
    leg_ik2fk = eval('bpy.ops.pose.rigify_leg_ik2fk_' + rig_id)
    arm_ik2fk = eval('bpy.ops.pose.rigify_arm_ik2fk_' + rig_id)

    controls = parse_bone_names(controls)
    ik_ctrl = parse_bone_names(ik_ctrl)
    fk_ctrl = parse_bone_names(fk_ctrl)
    parent = parse_bone_names(parent)
    pole = parse_bone_names(pole)

    pbones = bpy.context.selected_pose_bones
    bpy.ops.pose.select_all(action='DESELECT')

    for b in pbones:

        new_pole_vector_value = not rig.pose.bones[parent]['pole_vector']

        if b.name in controls or b.name in ik_ctrl:
            if limb_type == 'arm':
                func1 = arm_fk2ik
                func2 = arm_ik2fk
                rig.pose.bones[controls[0]].bone.select = not new_pole_vector_value
                rig.pose.bones[controls[4]].bone.select = not new_pole_vector_value
                rig.pose.bones[parent].bone.select = not new_pole_vector_value
                rig.pose.bones[pole].bone.select = new_pole_vector_value

                kwargs1 = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                          'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1],
                          'hand_ik': controls[4]}
                kwargs2 = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                          'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1], 'hand_ik': controls[4],
                          'pole': pole, 'main_parent': parent}
            else:
                func1 = leg_fk2ik
                func2 = leg_ik2fk
                rig.pose.bones[controls[0]].bone.select = not new_pole_vector_value
                rig.pose.bones[controls[6]].bone.select = not new_pole_vector_value
                rig.pose.bones[controls[5]].bone.select = not new_pole_vector_value
                rig.pose.bones[parent].bone.select = not new_pole_vector_value
                rig.pose.bones[pole].bone.select = new_pole_vector_value

                kwargs1 = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                          'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                          'foot_ik': ik_ctrl[2], 'mfoot_ik': ik_ctrl[2]}
                kwargs2 = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                          'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                          'foot_ik': controls[6], 'pole': pole, 'footroll': controls[5], 'mfoot_ik': ik_ctrl[2],
                          'main_parent': parent}

            func1(**kwargs1)
            rig.pose.bones[parent]['pole_vector'] = new_pole_vector_value
            func2(**kwargs2)

            bpy.ops.pose.select_all(action='DESELECT')
''']

REGISTER_OP_ARM_FKIK = ['Rigify_Arm_FK2IK', 'Rigify_Arm_IK2FK']

UTILITIES_OP_ARM_FKIK = ['''
##################################
## IK/FK Arm snapping operators ##
##################################

class Rigify_Arm_FK2IK(bpy.types.Operator):
    """ Snaps an FK arm to an IK arm.
    """
    bl_idname = "pose.rigify_arm_fk2ik_" + rig_id
    bl_label = "Rigify Snap FK arm to IK"
    bl_options = {'UNDO', 'INTERNAL'}

    uarm_fk: StringProperty(name="Upper Arm FK Name")
    farm_fk: StringProperty(name="Forerm FK Name")
    hand_fk: StringProperty(name="Hand FK Name")

    uarm_ik: StringProperty(name="Upper Arm IK Name")
    farm_ik: StringProperty(name="Forearm IK Name")
    hand_ik: StringProperty(name="Hand IK Name")

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.mode == 'POSE')

    def execute(self, context):
        fk2ik_arm(context.active_object, fk=[self.uarm_fk, self.farm_fk, self.hand_fk], ik=[self.uarm_ik, self.farm_ik, self.hand_ik])
        return {'FINISHED'}


class Rigify_Arm_IK2FK(bpy.types.Operator):
    """ Snaps an IK arm to an FK arm.
    """
    bl_idname = "pose.rigify_arm_ik2fk_" + rig_id
    bl_label = "Rigify Snap IK arm to FK"
    bl_options = {'UNDO', 'INTERNAL'}

    uarm_fk: StringProperty(name="Upper Arm FK Name")
    farm_fk: StringProperty(name="Forerm FK Name")
    hand_fk: StringProperty(name="Hand FK Name")

    uarm_ik: StringProperty(name="Upper Arm IK Name")
    farm_ik: StringProperty(name="Forearm IK Name")
    hand_ik: StringProperty(name="Hand IK Name")
    pole   : StringProperty(name="Pole IK Name")

    main_parent: StringProperty(name="Main Parent", default="")

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.mode == 'POSE')

    def execute(self, context):
        ik2fk_arm(context.active_object, fk=[self.uarm_fk, self.farm_fk, self.hand_fk], ik=[self.uarm_ik, self.farm_ik, self.hand_ik, self.pole, self.main_parent])
        return {'FINISHED'}
''']

REGISTER_OP_LEG_FKIK = ['Rigify_Leg_FK2IK', 'Rigify_Leg_IK2FK']

UTILITIES_OP_LEG_FKIK = ['''
##################################
## IK/FK Leg snapping operators ##
##################################

class Rigify_Leg_FK2IK(bpy.types.Operator):
    """ Snaps an FK leg to an IK leg.
    """
    bl_idname = "pose.rigify_leg_fk2ik_" + rig_id
    bl_label = "Rigify Snap FK leg to IK"
    bl_options = {'UNDO', 'INTERNAL'}

    thigh_fk: StringProperty(name="Thigh FK Name")
    shin_fk:  StringProperty(name="Shin FK Name")
    foot_fk:  StringProperty(name="Foot FK Name")
    mfoot_fk: StringProperty(name="MFoot FK Name")

    thigh_ik: StringProperty(name="Thigh IK Name")
    shin_ik:  StringProperty(name="Shin IK Name")
    foot_ik:  StringProperty(name="Foot IK Name")
    mfoot_ik: StringProperty(name="MFoot IK Name")

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.mode == 'POSE')

    def execute(self, context):
        fk2ik_leg(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.foot_fk, self.mfoot_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.mfoot_ik])
        return {'FINISHED'}


class Rigify_Leg_IK2FK(bpy.types.Operator):
    """ Snaps an IK leg to an FK leg.
    """
    bl_idname = "pose.rigify_leg_ik2fk_" + rig_id
    bl_label = "Rigify Snap IK leg to FK"
    bl_options = {'UNDO', 'INTERNAL'}

    thigh_fk: StringProperty(name="Thigh FK Name")
    shin_fk:  StringProperty(name="Shin FK Name")
    mfoot_fk: StringProperty(name="MFoot FK Name")
    foot_fk:  StringProperty(name="Foot FK Name", default="")
    thigh_ik: StringProperty(name="Thigh IK Name")
    shin_ik:  StringProperty(name="Shin IK Name")
    foot_ik:  StringProperty(name="Foot IK Name")
    footroll: StringProperty(name="Foot Roll Name")
    pole:     StringProperty(name="Pole IK Name")
    mfoot_ik: StringProperty(name="MFoot IK Name")

    main_parent: StringProperty(name="Main Parent", default="")

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.mode == 'POSE')

    def execute(self, context):
        ik2fk_leg(context.active_object, fk=[self.thigh_fk, self.shin_fk, self.mfoot_fk, self.foot_fk], ik=[self.thigh_ik, self.shin_ik, self.foot_ik, self.footroll, self.pole, self.mfoot_ik, self.main_parent])
        return {'FINISHED'}
''']

REGISTER_OP_POLE = ['Rigify_Rot2PoleSwitch']

UTILITIES_OP_POLE = ['''
###########################
## IK Rotation Pole Snap ##
###########################

class Rigify_Rot2PoleSwitch(bpy.types.Operator):
    bl_idname = "pose.rigify_rot2pole_" + rig_id
    bl_label = "Rotation - Pole toggle"
    bl_description = "Toggles IK chain between rotation and pole target"

    bone_name: StringProperty(default='')
    limb_type: StringProperty(name="Limb Type")
    controls: StringProperty(name="Controls string")
    ik_ctrl: StringProperty(name="IK Controls string")
    fk_ctrl: StringProperty(name="FK Controls string")
    parent: StringProperty(name="Parent name")
    pole: StringProperty(name="Pole name")

    def execute(self, context):
        rig = context.object

        if self.bone_name:
            bpy.ops.pose.select_all(action='DESELECT')
            rig.pose.bones[self.bone_name].bone.select = True

        rotPoleToggle(rig, self.limb_type, self.controls, self.ik_ctrl, self.fk_ctrl, self.parent, self.pole)
        return {'FINISHED'}
''']

REGISTER_RIG_ARM = REGISTER_OP_ARM_FKIK + REGISTER_OP_POLE

UTILITIES_RIG_ARM = [
    *UTILITIES_FUNC_ARM_FKIK,
    *UTILITIES_FUNC_POLE,
    *UTILITIES_OP_ARM_FKIK,
    *UTILITIES_OP_POLE,
]

REGISTER_RIG_LEG = REGISTER_OP_LEG_FKIK + REGISTER_OP_POLE

UTILITIES_RIG_LEG = [
    *UTILITIES_FUNC_LEG_FKIK,
    *UTILITIES_FUNC_POLE,
    *UTILITIES_OP_LEG_FKIK,
    *UTILITIES_OP_POLE,
]

##############################
## Default set of utilities ##
##############################

UI_REGISTER = [
    'RigUI',
    'RigLayers',
    *REGISTER_OP_ARM_FKIK,
    *REGISTER_OP_LEG_FKIK,
]

# Include arm and leg utilities for now in case somebody wants to use
# legacy limb rigs, which expect these to be available by default.
UI_UTILITIES = [
    *UTILITIES_FUNC_ARM_FKIK,
    *UTILITIES_FUNC_LEG_FKIK,
    *UTILITIES_OP_ARM_FKIK,
    *UTILITIES_OP_LEG_FKIK,
]

UI_SLIDERS = '''
###################
## Rig UI Panels ##
###################

class RigUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Rig Main Properties"
    bl_idname = "VIEW3D_PT_rig_ui_" + rig_id
    bl_category = 'Item'

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        try:
            return (context.active_object.data.get("rig_id") == rig_id)
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        pose_bones = context.active_object.pose.bones
        try:
            selected_bones = [bone.name for bone in context.selected_pose_bones]
            selected_bones += [context.active_pose_bone.name]
        except (AttributeError, TypeError):
            return

        def is_selected(names):
            # Returns whether any of the named bones are selected.
            if type(names) == list:
                for name in names:
                    if name in selected_bones:
                        return True
            elif names in selected_bones:
                return True
            return False


'''


def layers_ui(layers, layout):
    """ Turn a list of booleans + a list of names into a layer UI.
    """

    code = '''
class RigLayers(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Rig Layers"
    bl_idname = "VIEW3D_PT_rig_layers_" + rig_id
    bl_category = 'Item'

    @classmethod
    def poll(self, context):
        try:
            return (context.active_object.data.get("rig_id") == rig_id)
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        col = layout.column()
'''
    rows = {}
    for i in range(28):
        if layers[i]:
            if layout[i][1] not in rows:
                rows[layout[i][1]] = []
            rows[layout[i][1]] += [(layout[i][0], i)]

    keys = list(rows.keys())
    keys.sort()

    for key in keys:
        code += "\n        row = col.row()\n"
        i = 0
        for l in rows[key]:
            if i > 3:
                code += "\n        row = col.row()\n"
                i = 0
            code += "        row.prop(context.active_object.data, 'layers', index=%s, toggle=True, text='%s')\n" % (str(l[1]), l[0])
            i += 1

    # Root layer
    code += "\n        row = col.row()"
    code += "\n        row.separator()"
    code += "\n        row = col.row()"
    code += "\n        row.separator()\n"
    code += "\n        row = col.row()\n"
    code += "        row.prop(context.active_object.data, 'layers', index=28, toggle=True, text='Root')\n"

    return code
