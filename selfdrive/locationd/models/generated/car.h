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
void car_err_fun(double *nom_x, double *delta_x, double *out_8938065948081298282);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_2412018401198783436);
void car_H_mod_fun(double *state, double *out_8102122089500477321);
void car_f_fun(double *state, double dt, double *out_4032175873552877051);
void car_F_fun(double *state, double dt, double *out_8419527867095478295);
void car_h_25(double *state, double *unused, double *out_8790741933867989574);
void car_H_25(double *state, double *unused, double *out_3307291246572608212);
void car_h_24(double *state, double *unused, double *out_1160480957456784630);
void car_H_24(double *state, double *unused, double *out_1134641647567108646);
void car_h_30(double *state, double *unused, double *out_3488888099870427739);
void car_H_30(double *state, double *unused, double *out_5825624205079856839);
void car_h_26(double *state, double *unused, double *out_1512785167790417906);
void car_H_26(double *state, double *unused, double *out_434212072301448012);
void car_h_27(double *state, double *unused, double *out_3789068666207143929);
void car_H_27(double *state, double *unused, double *out_3650860893279431928);
void car_h_29(double *state, double *unused, double *out_3946255334558273074);
void car_H_29(double *state, double *unused, double *out_6335855549394249023);
void car_h_28(double *state, double *unused, double *out_7401531690408955978);
void car_H_28(double *state, double *unused, double *out_1253456532324718449);
void car_h_31(double *state, double *unused, double *out_7340110541239106407);
void car_H_31(double *state, double *unused, double *out_1060420174534799488);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}