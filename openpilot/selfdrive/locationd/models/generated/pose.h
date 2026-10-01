#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_err_fun(double *nom_x, double *delta_x, double *out_3159499921099066449);
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_6765203926591570612);
void pose_H_mod_fun(double *state, double *out_7470146636550372525);
void pose_f_fun(double *state, double dt, double *out_8463523398219764128);
void pose_F_fun(double *state, double dt, double *out_3788203468078225680);
void pose_h_4(double *state, double *unused, double *out_5084485555257631001);
void pose_H_4(double *state, double *unused, double *out_7702375358368229838);
void pose_h_10(double *state, double *unused, double *out_2120190459475098069);
void pose_H_10(double *state, double *unused, double *out_2259294001395867057);
void pose_h_13(double *state, double *unused, double *out_5269954238728557064);
void pose_H_13(double *state, double *unused, double *out_7532094890008988977);
void pose_h_14(double *state, double *unused, double *out_8523036253873003715);
void pose_H_14(double *state, double *unused, double *out_6781127859001837249);
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt);
}