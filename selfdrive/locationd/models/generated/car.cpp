#include "car.h"

namespace {
#define DIM 9
#define EDIM 9
#define MEDIM 9
typedef void (*Hfun)(double *, double *, double *);

double mass;

void set_mass(double x){ mass = x;}

double rotational_inertia;

void set_rotational_inertia(double x){ rotational_inertia = x;}

double center_to_front;

void set_center_to_front(double x){ center_to_front = x;}

double center_to_rear;

void set_center_to_rear(double x){ center_to_rear = x;}

double stiffness_front;

void set_stiffness_front(double x){ stiffness_front = x;}

double stiffness_rear;

void set_stiffness_rear(double x){ stiffness_rear = x;}
const static double MAHA_THRESH_25 = 3.8414588206941227;
const static double MAHA_THRESH_24 = 5.991464547107981;
const static double MAHA_THRESH_30 = 3.8414588206941227;
const static double MAHA_THRESH_26 = 3.8414588206941227;
const static double MAHA_THRESH_27 = 3.8414588206941227;
const static double MAHA_THRESH_29 = 3.8414588206941227;
const static double MAHA_THRESH_28 = 3.8414588206941227;
const static double MAHA_THRESH_31 = 3.8414588206941227;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_8938065948081298282) {
   out_8938065948081298282[0] = delta_x[0] + nom_x[0];
   out_8938065948081298282[1] = delta_x[1] + nom_x[1];
   out_8938065948081298282[2] = delta_x[2] + nom_x[2];
   out_8938065948081298282[3] = delta_x[3] + nom_x[3];
   out_8938065948081298282[4] = delta_x[4] + nom_x[4];
   out_8938065948081298282[5] = delta_x[5] + nom_x[5];
   out_8938065948081298282[6] = delta_x[6] + nom_x[6];
   out_8938065948081298282[7] = delta_x[7] + nom_x[7];
   out_8938065948081298282[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_2412018401198783436) {
   out_2412018401198783436[0] = -nom_x[0] + true_x[0];
   out_2412018401198783436[1] = -nom_x[1] + true_x[1];
   out_2412018401198783436[2] = -nom_x[2] + true_x[2];
   out_2412018401198783436[3] = -nom_x[3] + true_x[3];
   out_2412018401198783436[4] = -nom_x[4] + true_x[4];
   out_2412018401198783436[5] = -nom_x[5] + true_x[5];
   out_2412018401198783436[6] = -nom_x[6] + true_x[6];
   out_2412018401198783436[7] = -nom_x[7] + true_x[7];
   out_2412018401198783436[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_8102122089500477321) {
   out_8102122089500477321[0] = 1.0;
   out_8102122089500477321[1] = 0.0;
   out_8102122089500477321[2] = 0.0;
   out_8102122089500477321[3] = 0.0;
   out_8102122089500477321[4] = 0.0;
   out_8102122089500477321[5] = 0.0;
   out_8102122089500477321[6] = 0.0;
   out_8102122089500477321[7] = 0.0;
   out_8102122089500477321[8] = 0.0;
   out_8102122089500477321[9] = 0.0;
   out_8102122089500477321[10] = 1.0;
   out_8102122089500477321[11] = 0.0;
   out_8102122089500477321[12] = 0.0;
   out_8102122089500477321[13] = 0.0;
   out_8102122089500477321[14] = 0.0;
   out_8102122089500477321[15] = 0.0;
   out_8102122089500477321[16] = 0.0;
   out_8102122089500477321[17] = 0.0;
   out_8102122089500477321[18] = 0.0;
   out_8102122089500477321[19] = 0.0;
   out_8102122089500477321[20] = 1.0;
   out_8102122089500477321[21] = 0.0;
   out_8102122089500477321[22] = 0.0;
   out_8102122089500477321[23] = 0.0;
   out_8102122089500477321[24] = 0.0;
   out_8102122089500477321[25] = 0.0;
   out_8102122089500477321[26] = 0.0;
   out_8102122089500477321[27] = 0.0;
   out_8102122089500477321[28] = 0.0;
   out_8102122089500477321[29] = 0.0;
   out_8102122089500477321[30] = 1.0;
   out_8102122089500477321[31] = 0.0;
   out_8102122089500477321[32] = 0.0;
   out_8102122089500477321[33] = 0.0;
   out_8102122089500477321[34] = 0.0;
   out_8102122089500477321[35] = 0.0;
   out_8102122089500477321[36] = 0.0;
   out_8102122089500477321[37] = 0.0;
   out_8102122089500477321[38] = 0.0;
   out_8102122089500477321[39] = 0.0;
   out_8102122089500477321[40] = 1.0;
   out_8102122089500477321[41] = 0.0;
   out_8102122089500477321[42] = 0.0;
   out_8102122089500477321[43] = 0.0;
   out_8102122089500477321[44] = 0.0;
   out_8102122089500477321[45] = 0.0;
   out_8102122089500477321[46] = 0.0;
   out_8102122089500477321[47] = 0.0;
   out_8102122089500477321[48] = 0.0;
   out_8102122089500477321[49] = 0.0;
   out_8102122089500477321[50] = 1.0;
   out_8102122089500477321[51] = 0.0;
   out_8102122089500477321[52] = 0.0;
   out_8102122089500477321[53] = 0.0;
   out_8102122089500477321[54] = 0.0;
   out_8102122089500477321[55] = 0.0;
   out_8102122089500477321[56] = 0.0;
   out_8102122089500477321[57] = 0.0;
   out_8102122089500477321[58] = 0.0;
   out_8102122089500477321[59] = 0.0;
   out_8102122089500477321[60] = 1.0;
   out_8102122089500477321[61] = 0.0;
   out_8102122089500477321[62] = 0.0;
   out_8102122089500477321[63] = 0.0;
   out_8102122089500477321[64] = 0.0;
   out_8102122089500477321[65] = 0.0;
   out_8102122089500477321[66] = 0.0;
   out_8102122089500477321[67] = 0.0;
   out_8102122089500477321[68] = 0.0;
   out_8102122089500477321[69] = 0.0;
   out_8102122089500477321[70] = 1.0;
   out_8102122089500477321[71] = 0.0;
   out_8102122089500477321[72] = 0.0;
   out_8102122089500477321[73] = 0.0;
   out_8102122089500477321[74] = 0.0;
   out_8102122089500477321[75] = 0.0;
   out_8102122089500477321[76] = 0.0;
   out_8102122089500477321[77] = 0.0;
   out_8102122089500477321[78] = 0.0;
   out_8102122089500477321[79] = 0.0;
   out_8102122089500477321[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_4032175873552877051) {
   out_4032175873552877051[0] = state[0];
   out_4032175873552877051[1] = state[1];
   out_4032175873552877051[2] = state[2];
   out_4032175873552877051[3] = state[3];
   out_4032175873552877051[4] = state[4];
   out_4032175873552877051[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8000000000000007*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_4032175873552877051[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_4032175873552877051[7] = state[7];
   out_4032175873552877051[8] = state[8];
}
void F_fun(double *state, double dt, double *out_8419527867095478295) {
   out_8419527867095478295[0] = 1;
   out_8419527867095478295[1] = 0;
   out_8419527867095478295[2] = 0;
   out_8419527867095478295[3] = 0;
   out_8419527867095478295[4] = 0;
   out_8419527867095478295[5] = 0;
   out_8419527867095478295[6] = 0;
   out_8419527867095478295[7] = 0;
   out_8419527867095478295[8] = 0;
   out_8419527867095478295[9] = 0;
   out_8419527867095478295[10] = 1;
   out_8419527867095478295[11] = 0;
   out_8419527867095478295[12] = 0;
   out_8419527867095478295[13] = 0;
   out_8419527867095478295[14] = 0;
   out_8419527867095478295[15] = 0;
   out_8419527867095478295[16] = 0;
   out_8419527867095478295[17] = 0;
   out_8419527867095478295[18] = 0;
   out_8419527867095478295[19] = 0;
   out_8419527867095478295[20] = 1;
   out_8419527867095478295[21] = 0;
   out_8419527867095478295[22] = 0;
   out_8419527867095478295[23] = 0;
   out_8419527867095478295[24] = 0;
   out_8419527867095478295[25] = 0;
   out_8419527867095478295[26] = 0;
   out_8419527867095478295[27] = 0;
   out_8419527867095478295[28] = 0;
   out_8419527867095478295[29] = 0;
   out_8419527867095478295[30] = 1;
   out_8419527867095478295[31] = 0;
   out_8419527867095478295[32] = 0;
   out_8419527867095478295[33] = 0;
   out_8419527867095478295[34] = 0;
   out_8419527867095478295[35] = 0;
   out_8419527867095478295[36] = 0;
   out_8419527867095478295[37] = 0;
   out_8419527867095478295[38] = 0;
   out_8419527867095478295[39] = 0;
   out_8419527867095478295[40] = 1;
   out_8419527867095478295[41] = 0;
   out_8419527867095478295[42] = 0;
   out_8419527867095478295[43] = 0;
   out_8419527867095478295[44] = 0;
   out_8419527867095478295[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_8419527867095478295[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_8419527867095478295[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_8419527867095478295[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_8419527867095478295[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_8419527867095478295[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_8419527867095478295[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_8419527867095478295[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_8419527867095478295[53] = -9.8000000000000007*dt;
   out_8419527867095478295[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_8419527867095478295[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_8419527867095478295[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8419527867095478295[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8419527867095478295[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_8419527867095478295[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_8419527867095478295[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_8419527867095478295[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8419527867095478295[62] = 0;
   out_8419527867095478295[63] = 0;
   out_8419527867095478295[64] = 0;
   out_8419527867095478295[65] = 0;
   out_8419527867095478295[66] = 0;
   out_8419527867095478295[67] = 0;
   out_8419527867095478295[68] = 0;
   out_8419527867095478295[69] = 0;
   out_8419527867095478295[70] = 1;
   out_8419527867095478295[71] = 0;
   out_8419527867095478295[72] = 0;
   out_8419527867095478295[73] = 0;
   out_8419527867095478295[74] = 0;
   out_8419527867095478295[75] = 0;
   out_8419527867095478295[76] = 0;
   out_8419527867095478295[77] = 0;
   out_8419527867095478295[78] = 0;
   out_8419527867095478295[79] = 0;
   out_8419527867095478295[80] = 1;
}
void h_25(double *state, double *unused, double *out_8790741933867989574) {
   out_8790741933867989574[0] = state[6];
}
void H_25(double *state, double *unused, double *out_3307291246572608212) {
   out_3307291246572608212[0] = 0;
   out_3307291246572608212[1] = 0;
   out_3307291246572608212[2] = 0;
   out_3307291246572608212[3] = 0;
   out_3307291246572608212[4] = 0;
   out_3307291246572608212[5] = 0;
   out_3307291246572608212[6] = 1;
   out_3307291246572608212[7] = 0;
   out_3307291246572608212[8] = 0;
}
void h_24(double *state, double *unused, double *out_1160480957456784630) {
   out_1160480957456784630[0] = state[4];
   out_1160480957456784630[1] = state[5];
}
void H_24(double *state, double *unused, double *out_1134641647567108646) {
   out_1134641647567108646[0] = 0;
   out_1134641647567108646[1] = 0;
   out_1134641647567108646[2] = 0;
   out_1134641647567108646[3] = 0;
   out_1134641647567108646[4] = 1;
   out_1134641647567108646[5] = 0;
   out_1134641647567108646[6] = 0;
   out_1134641647567108646[7] = 0;
   out_1134641647567108646[8] = 0;
   out_1134641647567108646[9] = 0;
   out_1134641647567108646[10] = 0;
   out_1134641647567108646[11] = 0;
   out_1134641647567108646[12] = 0;
   out_1134641647567108646[13] = 0;
   out_1134641647567108646[14] = 1;
   out_1134641647567108646[15] = 0;
   out_1134641647567108646[16] = 0;
   out_1134641647567108646[17] = 0;
}
void h_30(double *state, double *unused, double *out_3488888099870427739) {
   out_3488888099870427739[0] = state[4];
}
void H_30(double *state, double *unused, double *out_5825624205079856839) {
   out_5825624205079856839[0] = 0;
   out_5825624205079856839[1] = 0;
   out_5825624205079856839[2] = 0;
   out_5825624205079856839[3] = 0;
   out_5825624205079856839[4] = 1;
   out_5825624205079856839[5] = 0;
   out_5825624205079856839[6] = 0;
   out_5825624205079856839[7] = 0;
   out_5825624205079856839[8] = 0;
}
void h_26(double *state, double *unused, double *out_1512785167790417906) {
   out_1512785167790417906[0] = state[7];
}
void H_26(double *state, double *unused, double *out_434212072301448012) {
   out_434212072301448012[0] = 0;
   out_434212072301448012[1] = 0;
   out_434212072301448012[2] = 0;
   out_434212072301448012[3] = 0;
   out_434212072301448012[4] = 0;
   out_434212072301448012[5] = 0;
   out_434212072301448012[6] = 0;
   out_434212072301448012[7] = 1;
   out_434212072301448012[8] = 0;
}
void h_27(double *state, double *unused, double *out_3789068666207143929) {
   out_3789068666207143929[0] = state[3];
}
void H_27(double *state, double *unused, double *out_3650860893279431928) {
   out_3650860893279431928[0] = 0;
   out_3650860893279431928[1] = 0;
   out_3650860893279431928[2] = 0;
   out_3650860893279431928[3] = 1;
   out_3650860893279431928[4] = 0;
   out_3650860893279431928[5] = 0;
   out_3650860893279431928[6] = 0;
   out_3650860893279431928[7] = 0;
   out_3650860893279431928[8] = 0;
}
void h_29(double *state, double *unused, double *out_3946255334558273074) {
   out_3946255334558273074[0] = state[1];
}
void H_29(double *state, double *unused, double *out_6335855549394249023) {
   out_6335855549394249023[0] = 0;
   out_6335855549394249023[1] = 1;
   out_6335855549394249023[2] = 0;
   out_6335855549394249023[3] = 0;
   out_6335855549394249023[4] = 0;
   out_6335855549394249023[5] = 0;
   out_6335855549394249023[6] = 0;
   out_6335855549394249023[7] = 0;
   out_6335855549394249023[8] = 0;
}
void h_28(double *state, double *unused, double *out_7401531690408955978) {
   out_7401531690408955978[0] = state[0];
}
void H_28(double *state, double *unused, double *out_1253456532324718449) {
   out_1253456532324718449[0] = 1;
   out_1253456532324718449[1] = 0;
   out_1253456532324718449[2] = 0;
   out_1253456532324718449[3] = 0;
   out_1253456532324718449[4] = 0;
   out_1253456532324718449[5] = 0;
   out_1253456532324718449[6] = 0;
   out_1253456532324718449[7] = 0;
   out_1253456532324718449[8] = 0;
}
void h_31(double *state, double *unused, double *out_7340110541239106407) {
   out_7340110541239106407[0] = state[8];
}
void H_31(double *state, double *unused, double *out_1060420174534799488) {
   out_1060420174534799488[0] = 0;
   out_1060420174534799488[1] = 0;
   out_1060420174534799488[2] = 0;
   out_1060420174534799488[3] = 0;
   out_1060420174534799488[4] = 0;
   out_1060420174534799488[5] = 0;
   out_1060420174534799488[6] = 0;
   out_1060420174534799488[7] = 0;
   out_1060420174534799488[8] = 1;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_25, H_25, NULL, in_z, in_R, in_ea, MAHA_THRESH_25);
}
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<2, 3, 0>(in_x, in_P, h_24, H_24, NULL, in_z, in_R, in_ea, MAHA_THRESH_24);
}
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_30, H_30, NULL, in_z, in_R, in_ea, MAHA_THRESH_30);
}
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_26, H_26, NULL, in_z, in_R, in_ea, MAHA_THRESH_26);
}
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_27, H_27, NULL, in_z, in_R, in_ea, MAHA_THRESH_27);
}
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_29, H_29, NULL, in_z, in_R, in_ea, MAHA_THRESH_29);
}
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_28, H_28, NULL, in_z, in_R, in_ea, MAHA_THRESH_28);
}
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_31, H_31, NULL, in_z, in_R, in_ea, MAHA_THRESH_31);
}
void car_err_fun(double *nom_x, double *delta_x, double *out_8938065948081298282) {
  err_fun(nom_x, delta_x, out_8938065948081298282);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_2412018401198783436) {
  inv_err_fun(nom_x, true_x, out_2412018401198783436);
}
void car_H_mod_fun(double *state, double *out_8102122089500477321) {
  H_mod_fun(state, out_8102122089500477321);
}
void car_f_fun(double *state, double dt, double *out_4032175873552877051) {
  f_fun(state,  dt, out_4032175873552877051);
}
void car_F_fun(double *state, double dt, double *out_8419527867095478295) {
  F_fun(state,  dt, out_8419527867095478295);
}
void car_h_25(double *state, double *unused, double *out_8790741933867989574) {
  h_25(state, unused, out_8790741933867989574);
}
void car_H_25(double *state, double *unused, double *out_3307291246572608212) {
  H_25(state, unused, out_3307291246572608212);
}
void car_h_24(double *state, double *unused, double *out_1160480957456784630) {
  h_24(state, unused, out_1160480957456784630);
}
void car_H_24(double *state, double *unused, double *out_1134641647567108646) {
  H_24(state, unused, out_1134641647567108646);
}
void car_h_30(double *state, double *unused, double *out_3488888099870427739) {
  h_30(state, unused, out_3488888099870427739);
}
void car_H_30(double *state, double *unused, double *out_5825624205079856839) {
  H_30(state, unused, out_5825624205079856839);
}
void car_h_26(double *state, double *unused, double *out_1512785167790417906) {
  h_26(state, unused, out_1512785167790417906);
}
void car_H_26(double *state, double *unused, double *out_434212072301448012) {
  H_26(state, unused, out_434212072301448012);
}
void car_h_27(double *state, double *unused, double *out_3789068666207143929) {
  h_27(state, unused, out_3789068666207143929);
}
void car_H_27(double *state, double *unused, double *out_3650860893279431928) {
  H_27(state, unused, out_3650860893279431928);
}
void car_h_29(double *state, double *unused, double *out_3946255334558273074) {
  h_29(state, unused, out_3946255334558273074);
}
void car_H_29(double *state, double *unused, double *out_6335855549394249023) {
  H_29(state, unused, out_6335855549394249023);
}
void car_h_28(double *state, double *unused, double *out_7401531690408955978) {
  h_28(state, unused, out_7401531690408955978);
}
void car_H_28(double *state, double *unused, double *out_1253456532324718449) {
  H_28(state, unused, out_1253456532324718449);
}
void car_h_31(double *state, double *unused, double *out_7340110541239106407) {
  h_31(state, unused, out_7340110541239106407);
}
void car_H_31(double *state, double *unused, double *out_1060420174534799488) {
  H_31(state, unused, out_1060420174534799488);
}
void car_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
void car_set_mass(double x) {
  set_mass(x);
}
void car_set_rotational_inertia(double x) {
  set_rotational_inertia(x);
}
void car_set_center_to_front(double x) {
  set_center_to_front(x);
}
void car_set_center_to_rear(double x) {
  set_center_to_rear(x);
}
void car_set_stiffness_front(double x) {
  set_stiffness_front(x);
}
void car_set_stiffness_rear(double x) {
  set_stiffness_rear(x);
}
}

const EKF car = {
  .name = "car",
  .kinds = { 25, 24, 30, 26, 27, 29, 28, 31 },
  .feature_kinds = {  },
  .f_fun = car_f_fun,
  .F_fun = car_F_fun,
  .err_fun = car_err_fun,
  .inv_err_fun = car_inv_err_fun,
  .H_mod_fun = car_H_mod_fun,
  .predict = car_predict,
  .hs = {
    { 25, car_h_25 },
    { 24, car_h_24 },
    { 30, car_h_30 },
    { 26, car_h_26 },
    { 27, car_h_27 },
    { 29, car_h_29 },
    { 28, car_h_28 },
    { 31, car_h_31 },
  },
  .Hs = {
    { 25, car_H_25 },
    { 24, car_H_24 },
    { 30, car_H_30 },
    { 26, car_H_26 },
    { 27, car_H_27 },
    { 29, car_H_29 },
    { 28, car_H_28 },
    { 31, car_H_31 },
  },
  .updates = {
    { 25, car_update_25 },
    { 24, car_update_24 },
    { 30, car_update_30 },
    { 26, car_update_26 },
    { 27, car_update_27 },
    { 29, car_update_29 },
    { 28, car_update_28 },
    { 31, car_update_31 },
  },
  .Hes = {
  },
  .sets = {
    { "mass", car_set_mass },
    { "rotational_inertia", car_set_rotational_inertia },
    { "center_to_front", car_set_center_to_front },
    { "center_to_rear", car_set_center_to_rear },
    { "stiffness_front", car_set_stiffness_front },
    { "stiffness_rear", car_set_stiffness_rear },
  },
  .extra_routines = {
  },
};

ekf_lib_init(car)
