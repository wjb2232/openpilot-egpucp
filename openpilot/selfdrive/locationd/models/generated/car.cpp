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
void err_fun(double *nom_x, double *delta_x, double *out_2049422539768281131) {
   out_2049422539768281131[0] = delta_x[0] + nom_x[0];
   out_2049422539768281131[1] = delta_x[1] + nom_x[1];
   out_2049422539768281131[2] = delta_x[2] + nom_x[2];
   out_2049422539768281131[3] = delta_x[3] + nom_x[3];
   out_2049422539768281131[4] = delta_x[4] + nom_x[4];
   out_2049422539768281131[5] = delta_x[5] + nom_x[5];
   out_2049422539768281131[6] = delta_x[6] + nom_x[6];
   out_2049422539768281131[7] = delta_x[7] + nom_x[7];
   out_2049422539768281131[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_6584761770466989213) {
   out_6584761770466989213[0] = -nom_x[0] + true_x[0];
   out_6584761770466989213[1] = -nom_x[1] + true_x[1];
   out_6584761770466989213[2] = -nom_x[2] + true_x[2];
   out_6584761770466989213[3] = -nom_x[3] + true_x[3];
   out_6584761770466989213[4] = -nom_x[4] + true_x[4];
   out_6584761770466989213[5] = -nom_x[5] + true_x[5];
   out_6584761770466989213[6] = -nom_x[6] + true_x[6];
   out_6584761770466989213[7] = -nom_x[7] + true_x[7];
   out_6584761770466989213[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_3521128072852066769) {
   out_3521128072852066769[0] = 1.0;
   out_3521128072852066769[1] = 0.0;
   out_3521128072852066769[2] = 0.0;
   out_3521128072852066769[3] = 0.0;
   out_3521128072852066769[4] = 0.0;
   out_3521128072852066769[5] = 0.0;
   out_3521128072852066769[6] = 0.0;
   out_3521128072852066769[7] = 0.0;
   out_3521128072852066769[8] = 0.0;
   out_3521128072852066769[9] = 0.0;
   out_3521128072852066769[10] = 1.0;
   out_3521128072852066769[11] = 0.0;
   out_3521128072852066769[12] = 0.0;
   out_3521128072852066769[13] = 0.0;
   out_3521128072852066769[14] = 0.0;
   out_3521128072852066769[15] = 0.0;
   out_3521128072852066769[16] = 0.0;
   out_3521128072852066769[17] = 0.0;
   out_3521128072852066769[18] = 0.0;
   out_3521128072852066769[19] = 0.0;
   out_3521128072852066769[20] = 1.0;
   out_3521128072852066769[21] = 0.0;
   out_3521128072852066769[22] = 0.0;
   out_3521128072852066769[23] = 0.0;
   out_3521128072852066769[24] = 0.0;
   out_3521128072852066769[25] = 0.0;
   out_3521128072852066769[26] = 0.0;
   out_3521128072852066769[27] = 0.0;
   out_3521128072852066769[28] = 0.0;
   out_3521128072852066769[29] = 0.0;
   out_3521128072852066769[30] = 1.0;
   out_3521128072852066769[31] = 0.0;
   out_3521128072852066769[32] = 0.0;
   out_3521128072852066769[33] = 0.0;
   out_3521128072852066769[34] = 0.0;
   out_3521128072852066769[35] = 0.0;
   out_3521128072852066769[36] = 0.0;
   out_3521128072852066769[37] = 0.0;
   out_3521128072852066769[38] = 0.0;
   out_3521128072852066769[39] = 0.0;
   out_3521128072852066769[40] = 1.0;
   out_3521128072852066769[41] = 0.0;
   out_3521128072852066769[42] = 0.0;
   out_3521128072852066769[43] = 0.0;
   out_3521128072852066769[44] = 0.0;
   out_3521128072852066769[45] = 0.0;
   out_3521128072852066769[46] = 0.0;
   out_3521128072852066769[47] = 0.0;
   out_3521128072852066769[48] = 0.0;
   out_3521128072852066769[49] = 0.0;
   out_3521128072852066769[50] = 1.0;
   out_3521128072852066769[51] = 0.0;
   out_3521128072852066769[52] = 0.0;
   out_3521128072852066769[53] = 0.0;
   out_3521128072852066769[54] = 0.0;
   out_3521128072852066769[55] = 0.0;
   out_3521128072852066769[56] = 0.0;
   out_3521128072852066769[57] = 0.0;
   out_3521128072852066769[58] = 0.0;
   out_3521128072852066769[59] = 0.0;
   out_3521128072852066769[60] = 1.0;
   out_3521128072852066769[61] = 0.0;
   out_3521128072852066769[62] = 0.0;
   out_3521128072852066769[63] = 0.0;
   out_3521128072852066769[64] = 0.0;
   out_3521128072852066769[65] = 0.0;
   out_3521128072852066769[66] = 0.0;
   out_3521128072852066769[67] = 0.0;
   out_3521128072852066769[68] = 0.0;
   out_3521128072852066769[69] = 0.0;
   out_3521128072852066769[70] = 1.0;
   out_3521128072852066769[71] = 0.0;
   out_3521128072852066769[72] = 0.0;
   out_3521128072852066769[73] = 0.0;
   out_3521128072852066769[74] = 0.0;
   out_3521128072852066769[75] = 0.0;
   out_3521128072852066769[76] = 0.0;
   out_3521128072852066769[77] = 0.0;
   out_3521128072852066769[78] = 0.0;
   out_3521128072852066769[79] = 0.0;
   out_3521128072852066769[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_7234002911528481902) {
   out_7234002911528481902[0] = state[0];
   out_7234002911528481902[1] = state[1];
   out_7234002911528481902[2] = state[2];
   out_7234002911528481902[3] = state[3];
   out_7234002911528481902[4] = state[4];
   out_7234002911528481902[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8100000000000005*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_7234002911528481902[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_7234002911528481902[7] = state[7];
   out_7234002911528481902[8] = state[8];
}
void F_fun(double *state, double dt, double *out_6589042199508768395) {
   out_6589042199508768395[0] = 1;
   out_6589042199508768395[1] = 0;
   out_6589042199508768395[2] = 0;
   out_6589042199508768395[3] = 0;
   out_6589042199508768395[4] = 0;
   out_6589042199508768395[5] = 0;
   out_6589042199508768395[6] = 0;
   out_6589042199508768395[7] = 0;
   out_6589042199508768395[8] = 0;
   out_6589042199508768395[9] = 0;
   out_6589042199508768395[10] = 1;
   out_6589042199508768395[11] = 0;
   out_6589042199508768395[12] = 0;
   out_6589042199508768395[13] = 0;
   out_6589042199508768395[14] = 0;
   out_6589042199508768395[15] = 0;
   out_6589042199508768395[16] = 0;
   out_6589042199508768395[17] = 0;
   out_6589042199508768395[18] = 0;
   out_6589042199508768395[19] = 0;
   out_6589042199508768395[20] = 1;
   out_6589042199508768395[21] = 0;
   out_6589042199508768395[22] = 0;
   out_6589042199508768395[23] = 0;
   out_6589042199508768395[24] = 0;
   out_6589042199508768395[25] = 0;
   out_6589042199508768395[26] = 0;
   out_6589042199508768395[27] = 0;
   out_6589042199508768395[28] = 0;
   out_6589042199508768395[29] = 0;
   out_6589042199508768395[30] = 1;
   out_6589042199508768395[31] = 0;
   out_6589042199508768395[32] = 0;
   out_6589042199508768395[33] = 0;
   out_6589042199508768395[34] = 0;
   out_6589042199508768395[35] = 0;
   out_6589042199508768395[36] = 0;
   out_6589042199508768395[37] = 0;
   out_6589042199508768395[38] = 0;
   out_6589042199508768395[39] = 0;
   out_6589042199508768395[40] = 1;
   out_6589042199508768395[41] = 0;
   out_6589042199508768395[42] = 0;
   out_6589042199508768395[43] = 0;
   out_6589042199508768395[44] = 0;
   out_6589042199508768395[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_6589042199508768395[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_6589042199508768395[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_6589042199508768395[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_6589042199508768395[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_6589042199508768395[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_6589042199508768395[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_6589042199508768395[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_6589042199508768395[53] = -9.8100000000000005*dt;
   out_6589042199508768395[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_6589042199508768395[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_6589042199508768395[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_6589042199508768395[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_6589042199508768395[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_6589042199508768395[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_6589042199508768395[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_6589042199508768395[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_6589042199508768395[62] = 0;
   out_6589042199508768395[63] = 0;
   out_6589042199508768395[64] = 0;
   out_6589042199508768395[65] = 0;
   out_6589042199508768395[66] = 0;
   out_6589042199508768395[67] = 0;
   out_6589042199508768395[68] = 0;
   out_6589042199508768395[69] = 0;
   out_6589042199508768395[70] = 1;
   out_6589042199508768395[71] = 0;
   out_6589042199508768395[72] = 0;
   out_6589042199508768395[73] = 0;
   out_6589042199508768395[74] = 0;
   out_6589042199508768395[75] = 0;
   out_6589042199508768395[76] = 0;
   out_6589042199508768395[77] = 0;
   out_6589042199508768395[78] = 0;
   out_6589042199508768395[79] = 0;
   out_6589042199508768395[80] = 1;
}
void h_25(double *state, double *unused, double *out_7649812094543452430) {
   out_7649812094543452430[0] = state[6];
}
void H_25(double *state, double *unused, double *out_1852577137424908) {
   out_1852577137424908[0] = 0;
   out_1852577137424908[1] = 0;
   out_1852577137424908[2] = 0;
   out_1852577137424908[3] = 0;
   out_1852577137424908[4] = 0;
   out_1852577137424908[5] = 0;
   out_1852577137424908[6] = 1;
   out_1852577137424908[7] = 0;
   out_1852577137424908[8] = 0;
}
void h_24(double *state, double *unused, double *out_3256603922105750952) {
   out_3256603922105750952[0] = state[4];
   out_3256603922105750952[1] = state[5];
}
void H_24(double *state, double *unused, double *out_3559778175939748044) {
   out_3559778175939748044[0] = 0;
   out_3559778175939748044[1] = 0;
   out_3559778175939748044[2] = 0;
   out_3559778175939748044[3] = 0;
   out_3559778175939748044[4] = 1;
   out_3559778175939748044[5] = 0;
   out_3559778175939748044[6] = 0;
   out_3559778175939748044[7] = 0;
   out_3559778175939748044[8] = 0;
   out_3559778175939748044[9] = 0;
   out_3559778175939748044[10] = 0;
   out_3559778175939748044[11] = 0;
   out_3559778175939748044[12] = 0;
   out_3559778175939748044[13] = 0;
   out_3559778175939748044[14] = 1;
   out_3559778175939748044[15] = 0;
   out_3559778175939748044[16] = 0;
   out_3559778175939748044[17] = 0;
}
void h_30(double *state, double *unused, double *out_878976868193101494) {
   out_878976868193101494[0] = state[4];
}
void H_30(double *state, double *unused, double *out_6918542918629041663) {
   out_6918542918629041663[0] = 0;
   out_6918542918629041663[1] = 0;
   out_6918542918629041663[2] = 0;
   out_6918542918629041663[3] = 0;
   out_6918542918629041663[4] = 1;
   out_6918542918629041663[5] = 0;
   out_6918542918629041663[6] = 0;
   out_6918542918629041663[7] = 0;
   out_6918542918629041663[8] = 0;
}
void h_26(double *state, double *unused, double *out_1822486721094763929) {
   out_1822486721094763929[0] = state[7];
}
void H_26(double *state, double *unused, double *out_3739650741736631316) {
   out_3739650741736631316[0] = 0;
   out_3739650741736631316[1] = 0;
   out_3739650741736631316[2] = 0;
   out_3739650741736631316[3] = 0;
   out_3739650741736631316[4] = 0;
   out_3739650741736631316[5] = 0;
   out_3739650741736631316[6] = 0;
   out_3739650741736631316[7] = 1;
   out_3739650741736631316[8] = 0;
}
void h_27(double *state, double *unused, double *out_5795258711505253541) {
   out_5795258711505253541[0] = state[3];
}
void H_27(double *state, double *unused, double *out_4743779606828616752) {
   out_4743779606828616752[0] = 0;
   out_4743779606828616752[1] = 0;
   out_4743779606828616752[2] = 0;
   out_4743779606828616752[3] = 1;
   out_4743779606828616752[4] = 0;
   out_4743779606828616752[5] = 0;
   out_4743779606828616752[6] = 0;
   out_4743779606828616752[7] = 0;
   out_4743779606828616752[8] = 0;
}
void h_29(double *state, double *unused, double *out_5880650135853947139) {
   out_5880650135853947139[0] = state[1];
}
void H_29(double *state, double *unused, double *out_7428774262943433847) {
   out_7428774262943433847[0] = 0;
   out_7428774262943433847[1] = 1;
   out_7428774262943433847[2] = 0;
   out_7428774262943433847[3] = 0;
   out_7428774262943433847[4] = 0;
   out_7428774262943433847[5] = 0;
   out_7428774262943433847[6] = 0;
   out_7428774262943433847[7] = 0;
   out_7428774262943433847[8] = 0;
}
void h_28(double *state, double *unused, double *out_7485706546240934501) {
   out_7485706546240934501[0] = state[0];
}
void H_28(double *state, double *unused, double *out_2346375245873903273) {
   out_2346375245873903273[0] = 1;
   out_2346375245873903273[1] = 0;
   out_2346375245873903273[2] = 0;
   out_2346375245873903273[3] = 0;
   out_2346375245873903273[4] = 0;
   out_2346375245873903273[5] = 0;
   out_2346375245873903273[6] = 0;
   out_2346375245873903273[7] = 0;
   out_2346375245873903273[8] = 0;
}
void h_31(double *state, double *unused, double *out_4702086104187967469) {
   out_4702086104187967469[0] = state[8];
}
void H_31(double *state, double *unused, double *out_32498539014385336) {
   out_32498539014385336[0] = 0;
   out_32498539014385336[1] = 0;
   out_32498539014385336[2] = 0;
   out_32498539014385336[3] = 0;
   out_32498539014385336[4] = 0;
   out_32498539014385336[5] = 0;
   out_32498539014385336[6] = 0;
   out_32498539014385336[7] = 0;
   out_32498539014385336[8] = 1;
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
void car_err_fun(double *nom_x, double *delta_x, double *out_2049422539768281131) {
  err_fun(nom_x, delta_x, out_2049422539768281131);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_6584761770466989213) {
  inv_err_fun(nom_x, true_x, out_6584761770466989213);
}
void car_H_mod_fun(double *state, double *out_3521128072852066769) {
  H_mod_fun(state, out_3521128072852066769);
}
void car_f_fun(double *state, double dt, double *out_7234002911528481902) {
  f_fun(state,  dt, out_7234002911528481902);
}
void car_F_fun(double *state, double dt, double *out_6589042199508768395) {
  F_fun(state,  dt, out_6589042199508768395);
}
void car_h_25(double *state, double *unused, double *out_7649812094543452430) {
  h_25(state, unused, out_7649812094543452430);
}
void car_H_25(double *state, double *unused, double *out_1852577137424908) {
  H_25(state, unused, out_1852577137424908);
}
void car_h_24(double *state, double *unused, double *out_3256603922105750952) {
  h_24(state, unused, out_3256603922105750952);
}
void car_H_24(double *state, double *unused, double *out_3559778175939748044) {
  H_24(state, unused, out_3559778175939748044);
}
void car_h_30(double *state, double *unused, double *out_878976868193101494) {
  h_30(state, unused, out_878976868193101494);
}
void car_H_30(double *state, double *unused, double *out_6918542918629041663) {
  H_30(state, unused, out_6918542918629041663);
}
void car_h_26(double *state, double *unused, double *out_1822486721094763929) {
  h_26(state, unused, out_1822486721094763929);
}
void car_H_26(double *state, double *unused, double *out_3739650741736631316) {
  H_26(state, unused, out_3739650741736631316);
}
void car_h_27(double *state, double *unused, double *out_5795258711505253541) {
  h_27(state, unused, out_5795258711505253541);
}
void car_H_27(double *state, double *unused, double *out_4743779606828616752) {
  H_27(state, unused, out_4743779606828616752);
}
void car_h_29(double *state, double *unused, double *out_5880650135853947139) {
  h_29(state, unused, out_5880650135853947139);
}
void car_H_29(double *state, double *unused, double *out_7428774262943433847) {
  H_29(state, unused, out_7428774262943433847);
}
void car_h_28(double *state, double *unused, double *out_7485706546240934501) {
  h_28(state, unused, out_7485706546240934501);
}
void car_H_28(double *state, double *unused, double *out_2346375245873903273) {
  H_28(state, unused, out_2346375245873903273);
}
void car_h_31(double *state, double *unused, double *out_4702086104187967469) {
  h_31(state, unused, out_4702086104187967469);
}
void car_H_31(double *state, double *unused, double *out_32498539014385336) {
  H_31(state, unused, out_32498539014385336);
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
