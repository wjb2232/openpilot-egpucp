#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_err_fun(double *nom_x, double *delta_x, double *out_2049422539768281131);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_6584761770466989213);
void car_H_mod_fun(double *state, double *out_3521128072852066769);
void car_f_fun(double *state, double dt, double *out_7234002911528481902);
void car_F_fun(double *state, double dt, double *out_6589042199508768395);
void car_h_25(double *state, double *unused, double *out_7649812094543452430);
void car_H_25(double *state, double *unused, double *out_1852577137424908);
void car_h_24(double *state, double *unused, double *out_3256603922105750952);
void car_H_24(double *state, double *unused, double *out_3559778175939748044);
void car_h_30(double *state, double *unused, double *out_878976868193101494);
void car_H_30(double *state, double *unused, double *out_6918542918629041663);
void car_h_26(double *state, double *unused, double *out_1822486721094763929);
void car_H_26(double *state, double *unused, double *out_3739650741736631316);
void car_h_27(double *state, double *unused, double *out_5795258711505253541);
void car_H_27(double *state, double *unused, double *out_4743779606828616752);
void car_h_29(double *state, double *unused, double *out_5880650135853947139);
void car_H_29(double *state, double *unused, double *out_7428774262943433847);
void car_h_28(double *state, double *unused, double *out_7485706546240934501);
void car_H_28(double *state, double *unused, double *out_2346375245873903273);
void car_h_31(double *state, double *unused, double *out_4702086104187967469);
void car_H_31(double *state, double *unused, double *out_32498539014385336);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}