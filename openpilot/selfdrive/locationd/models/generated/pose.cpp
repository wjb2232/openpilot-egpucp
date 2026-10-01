#include "pose.h"

namespace {
#define DIM 18
#define EDIM 18
#define MEDIM 18
typedef void (*Hfun)(double *, double *, double *);
const static double MAHA_THRESH_4 = 7.814727903251177;
const static double MAHA_THRESH_10 = 7.814727903251177;
const static double MAHA_THRESH_13 = 7.814727903251177;
const static double MAHA_THRESH_14 = 7.814727903251177;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_3159499921099066449) {
   out_3159499921099066449[0] = delta_x[0] + nom_x[0];
   out_3159499921099066449[1] = delta_x[1] + nom_x[1];
   out_3159499921099066449[2] = delta_x[2] + nom_x[2];
   out_3159499921099066449[3] = delta_x[3] + nom_x[3];
   out_3159499921099066449[4] = delta_x[4] + nom_x[4];
   out_3159499921099066449[5] = delta_x[5] + nom_x[5];
   out_3159499921099066449[6] = delta_x[6] + nom_x[6];
   out_3159499921099066449[7] = delta_x[7] + nom_x[7];
   out_3159499921099066449[8] = delta_x[8] + nom_x[8];
   out_3159499921099066449[9] = delta_x[9] + nom_x[9];
   out_3159499921099066449[10] = delta_x[10] + nom_x[10];
   out_3159499921099066449[11] = delta_x[11] + nom_x[11];
   out_3159499921099066449[12] = delta_x[12] + nom_x[12];
   out_3159499921099066449[13] = delta_x[13] + nom_x[13];
   out_3159499921099066449[14] = delta_x[14] + nom_x[14];
   out_3159499921099066449[15] = delta_x[15] + nom_x[15];
   out_3159499921099066449[16] = delta_x[16] + nom_x[16];
   out_3159499921099066449[17] = delta_x[17] + nom_x[17];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_6765203926591570612) {
   out_6765203926591570612[0] = -nom_x[0] + true_x[0];
   out_6765203926591570612[1] = -nom_x[1] + true_x[1];
   out_6765203926591570612[2] = -nom_x[2] + true_x[2];
   out_6765203926591570612[3] = -nom_x[3] + true_x[3];
   out_6765203926591570612[4] = -nom_x[4] + true_x[4];
   out_6765203926591570612[5] = -nom_x[5] + true_x[5];
   out_6765203926591570612[6] = -nom_x[6] + true_x[6];
   out_6765203926591570612[7] = -nom_x[7] + true_x[7];
   out_6765203926591570612[8] = -nom_x[8] + true_x[8];
   out_6765203926591570612[9] = -nom_x[9] + true_x[9];
   out_6765203926591570612[10] = -nom_x[10] + true_x[10];
   out_6765203926591570612[11] = -nom_x[11] + true_x[11];
   out_6765203926591570612[12] = -nom_x[12] + true_x[12];
   out_6765203926591570612[13] = -nom_x[13] + true_x[13];
   out_6765203926591570612[14] = -nom_x[14] + true_x[14];
   out_6765203926591570612[15] = -nom_x[15] + true_x[15];
   out_6765203926591570612[16] = -nom_x[16] + true_x[16];
   out_6765203926591570612[17] = -nom_x[17] + true_x[17];
}
void H_mod_fun(double *state, double *out_7470146636550372525) {
   out_7470146636550372525[0] = 1.0;
   out_7470146636550372525[1] = 0.0;
   out_7470146636550372525[2] = 0.0;
   out_7470146636550372525[3] = 0.0;
   out_7470146636550372525[4] = 0.0;
   out_7470146636550372525[5] = 0.0;
   out_7470146636550372525[6] = 0.0;
   out_7470146636550372525[7] = 0.0;
   out_7470146636550372525[8] = 0.0;
   out_7470146636550372525[9] = 0.0;
   out_7470146636550372525[10] = 0.0;
   out_7470146636550372525[11] = 0.0;
   out_7470146636550372525[12] = 0.0;
   out_7470146636550372525[13] = 0.0;
   out_7470146636550372525[14] = 0.0;
   out_7470146636550372525[15] = 0.0;
   out_7470146636550372525[16] = 0.0;
   out_7470146636550372525[17] = 0.0;
   out_7470146636550372525[18] = 0.0;
   out_7470146636550372525[19] = 1.0;
   out_7470146636550372525[20] = 0.0;
   out_7470146636550372525[21] = 0.0;
   out_7470146636550372525[22] = 0.0;
   out_7470146636550372525[23] = 0.0;
   out_7470146636550372525[24] = 0.0;
   out_7470146636550372525[25] = 0.0;
   out_7470146636550372525[26] = 0.0;
   out_7470146636550372525[27] = 0.0;
   out_7470146636550372525[28] = 0.0;
   out_7470146636550372525[29] = 0.0;
   out_7470146636550372525[30] = 0.0;
   out_7470146636550372525[31] = 0.0;
   out_7470146636550372525[32] = 0.0;
   out_7470146636550372525[33] = 0.0;
   out_7470146636550372525[34] = 0.0;
   out_7470146636550372525[35] = 0.0;
   out_7470146636550372525[36] = 0.0;
   out_7470146636550372525[37] = 0.0;
   out_7470146636550372525[38] = 1.0;
   out_7470146636550372525[39] = 0.0;
   out_7470146636550372525[40] = 0.0;
   out_7470146636550372525[41] = 0.0;
   out_7470146636550372525[42] = 0.0;
   out_7470146636550372525[43] = 0.0;
   out_7470146636550372525[44] = 0.0;
   out_7470146636550372525[45] = 0.0;
   out_7470146636550372525[46] = 0.0;
   out_7470146636550372525[47] = 0.0;
   out_7470146636550372525[48] = 0.0;
   out_7470146636550372525[49] = 0.0;
   out_7470146636550372525[50] = 0.0;
   out_7470146636550372525[51] = 0.0;
   out_7470146636550372525[52] = 0.0;
   out_7470146636550372525[53] = 0.0;
   out_7470146636550372525[54] = 0.0;
   out_7470146636550372525[55] = 0.0;
   out_7470146636550372525[56] = 0.0;
   out_7470146636550372525[57] = 1.0;
   out_7470146636550372525[58] = 0.0;
   out_7470146636550372525[59] = 0.0;
   out_7470146636550372525[60] = 0.0;
   out_7470146636550372525[61] = 0.0;
   out_7470146636550372525[62] = 0.0;
   out_7470146636550372525[63] = 0.0;
   out_7470146636550372525[64] = 0.0;
   out_7470146636550372525[65] = 0.0;
   out_7470146636550372525[66] = 0.0;
   out_7470146636550372525[67] = 0.0;
   out_7470146636550372525[68] = 0.0;
   out_7470146636550372525[69] = 0.0;
   out_7470146636550372525[70] = 0.0;
   out_7470146636550372525[71] = 0.0;
   out_7470146636550372525[72] = 0.0;
   out_7470146636550372525[73] = 0.0;
   out_7470146636550372525[74] = 0.0;
   out_7470146636550372525[75] = 0.0;
   out_7470146636550372525[76] = 1.0;
   out_7470146636550372525[77] = 0.0;
   out_7470146636550372525[78] = 0.0;
   out_7470146636550372525[79] = 0.0;
   out_7470146636550372525[80] = 0.0;
   out_7470146636550372525[81] = 0.0;
   out_7470146636550372525[82] = 0.0;
   out_7470146636550372525[83] = 0.0;
   out_7470146636550372525[84] = 0.0;
   out_7470146636550372525[85] = 0.0;
   out_7470146636550372525[86] = 0.0;
   out_7470146636550372525[87] = 0.0;
   out_7470146636550372525[88] = 0.0;
   out_7470146636550372525[89] = 0.0;
   out_7470146636550372525[90] = 0.0;
   out_7470146636550372525[91] = 0.0;
   out_7470146636550372525[92] = 0.0;
   out_7470146636550372525[93] = 0.0;
   out_7470146636550372525[94] = 0.0;
   out_7470146636550372525[95] = 1.0;
   out_7470146636550372525[96] = 0.0;
   out_7470146636550372525[97] = 0.0;
   out_7470146636550372525[98] = 0.0;
   out_7470146636550372525[99] = 0.0;
   out_7470146636550372525[100] = 0.0;
   out_7470146636550372525[101] = 0.0;
   out_7470146636550372525[102] = 0.0;
   out_7470146636550372525[103] = 0.0;
   out_7470146636550372525[104] = 0.0;
   out_7470146636550372525[105] = 0.0;
   out_7470146636550372525[106] = 0.0;
   out_7470146636550372525[107] = 0.0;
   out_7470146636550372525[108] = 0.0;
   out_7470146636550372525[109] = 0.0;
   out_7470146636550372525[110] = 0.0;
   out_7470146636550372525[111] = 0.0;
   out_7470146636550372525[112] = 0.0;
   out_7470146636550372525[113] = 0.0;
   out_7470146636550372525[114] = 1.0;
   out_7470146636550372525[115] = 0.0;
   out_7470146636550372525[116] = 0.0;
   out_7470146636550372525[117] = 0.0;
   out_7470146636550372525[118] = 0.0;
   out_7470146636550372525[119] = 0.0;
   out_7470146636550372525[120] = 0.0;
   out_7470146636550372525[121] = 0.0;
   out_7470146636550372525[122] = 0.0;
   out_7470146636550372525[123] = 0.0;
   out_7470146636550372525[124] = 0.0;
   out_7470146636550372525[125] = 0.0;
   out_7470146636550372525[126] = 0.0;
   out_7470146636550372525[127] = 0.0;
   out_7470146636550372525[128] = 0.0;
   out_7470146636550372525[129] = 0.0;
   out_7470146636550372525[130] = 0.0;
   out_7470146636550372525[131] = 0.0;
   out_7470146636550372525[132] = 0.0;
   out_7470146636550372525[133] = 1.0;
   out_7470146636550372525[134] = 0.0;
   out_7470146636550372525[135] = 0.0;
   out_7470146636550372525[136] = 0.0;
   out_7470146636550372525[137] = 0.0;
   out_7470146636550372525[138] = 0.0;
   out_7470146636550372525[139] = 0.0;
   out_7470146636550372525[140] = 0.0;
   out_7470146636550372525[141] = 0.0;
   out_7470146636550372525[142] = 0.0;
   out_7470146636550372525[143] = 0.0;
   out_7470146636550372525[144] = 0.0;
   out_7470146636550372525[145] = 0.0;
   out_7470146636550372525[146] = 0.0;
   out_7470146636550372525[147] = 0.0;
   out_7470146636550372525[148] = 0.0;
   out_7470146636550372525[149] = 0.0;
   out_7470146636550372525[150] = 0.0;
   out_7470146636550372525[151] = 0.0;
   out_7470146636550372525[152] = 1.0;
   out_7470146636550372525[153] = 0.0;
   out_7470146636550372525[154] = 0.0;
   out_7470146636550372525[155] = 0.0;
   out_7470146636550372525[156] = 0.0;
   out_7470146636550372525[157] = 0.0;
   out_7470146636550372525[158] = 0.0;
   out_7470146636550372525[159] = 0.0;
   out_7470146636550372525[160] = 0.0;
   out_7470146636550372525[161] = 0.0;
   out_7470146636550372525[162] = 0.0;
   out_7470146636550372525[163] = 0.0;
   out_7470146636550372525[164] = 0.0;
   out_7470146636550372525[165] = 0.0;
   out_7470146636550372525[166] = 0.0;
   out_7470146636550372525[167] = 0.0;
   out_7470146636550372525[168] = 0.0;
   out_7470146636550372525[169] = 0.0;
   out_7470146636550372525[170] = 0.0;
   out_7470146636550372525[171] = 1.0;
   out_7470146636550372525[172] = 0.0;
   out_7470146636550372525[173] = 0.0;
   out_7470146636550372525[174] = 0.0;
   out_7470146636550372525[175] = 0.0;
   out_7470146636550372525[176] = 0.0;
   out_7470146636550372525[177] = 0.0;
   out_7470146636550372525[178] = 0.0;
   out_7470146636550372525[179] = 0.0;
   out_7470146636550372525[180] = 0.0;
   out_7470146636550372525[181] = 0.0;
   out_7470146636550372525[182] = 0.0;
   out_7470146636550372525[183] = 0.0;
   out_7470146636550372525[184] = 0.0;
   out_7470146636550372525[185] = 0.0;
   out_7470146636550372525[186] = 0.0;
   out_7470146636550372525[187] = 0.0;
   out_7470146636550372525[188] = 0.0;
   out_7470146636550372525[189] = 0.0;
   out_7470146636550372525[190] = 1.0;
   out_7470146636550372525[191] = 0.0;
   out_7470146636550372525[192] = 0.0;
   out_7470146636550372525[193] = 0.0;
   out_7470146636550372525[194] = 0.0;
   out_7470146636550372525[195] = 0.0;
   out_7470146636550372525[196] = 0.0;
   out_7470146636550372525[197] = 0.0;
   out_7470146636550372525[198] = 0.0;
   out_7470146636550372525[199] = 0.0;
   out_7470146636550372525[200] = 0.0;
   out_7470146636550372525[201] = 0.0;
   out_7470146636550372525[202] = 0.0;
   out_7470146636550372525[203] = 0.0;
   out_7470146636550372525[204] = 0.0;
   out_7470146636550372525[205] = 0.0;
   out_7470146636550372525[206] = 0.0;
   out_7470146636550372525[207] = 0.0;
   out_7470146636550372525[208] = 0.0;
   out_7470146636550372525[209] = 1.0;
   out_7470146636550372525[210] = 0.0;
   out_7470146636550372525[211] = 0.0;
   out_7470146636550372525[212] = 0.0;
   out_7470146636550372525[213] = 0.0;
   out_7470146636550372525[214] = 0.0;
   out_7470146636550372525[215] = 0.0;
   out_7470146636550372525[216] = 0.0;
   out_7470146636550372525[217] = 0.0;
   out_7470146636550372525[218] = 0.0;
   out_7470146636550372525[219] = 0.0;
   out_7470146636550372525[220] = 0.0;
   out_7470146636550372525[221] = 0.0;
   out_7470146636550372525[222] = 0.0;
   out_7470146636550372525[223] = 0.0;
   out_7470146636550372525[224] = 0.0;
   out_7470146636550372525[225] = 0.0;
   out_7470146636550372525[226] = 0.0;
   out_7470146636550372525[227] = 0.0;
   out_7470146636550372525[228] = 1.0;
   out_7470146636550372525[229] = 0.0;
   out_7470146636550372525[230] = 0.0;
   out_7470146636550372525[231] = 0.0;
   out_7470146636550372525[232] = 0.0;
   out_7470146636550372525[233] = 0.0;
   out_7470146636550372525[234] = 0.0;
   out_7470146636550372525[235] = 0.0;
   out_7470146636550372525[236] = 0.0;
   out_7470146636550372525[237] = 0.0;
   out_7470146636550372525[238] = 0.0;
   out_7470146636550372525[239] = 0.0;
   out_7470146636550372525[240] = 0.0;
   out_7470146636550372525[241] = 0.0;
   out_7470146636550372525[242] = 0.0;
   out_7470146636550372525[243] = 0.0;
   out_7470146636550372525[244] = 0.0;
   out_7470146636550372525[245] = 0.0;
   out_7470146636550372525[246] = 0.0;
   out_7470146636550372525[247] = 1.0;
   out_7470146636550372525[248] = 0.0;
   out_7470146636550372525[249] = 0.0;
   out_7470146636550372525[250] = 0.0;
   out_7470146636550372525[251] = 0.0;
   out_7470146636550372525[252] = 0.0;
   out_7470146636550372525[253] = 0.0;
   out_7470146636550372525[254] = 0.0;
   out_7470146636550372525[255] = 0.0;
   out_7470146636550372525[256] = 0.0;
   out_7470146636550372525[257] = 0.0;
   out_7470146636550372525[258] = 0.0;
   out_7470146636550372525[259] = 0.0;
   out_7470146636550372525[260] = 0.0;
   out_7470146636550372525[261] = 0.0;
   out_7470146636550372525[262] = 0.0;
   out_7470146636550372525[263] = 0.0;
   out_7470146636550372525[264] = 0.0;
   out_7470146636550372525[265] = 0.0;
   out_7470146636550372525[266] = 1.0;
   out_7470146636550372525[267] = 0.0;
   out_7470146636550372525[268] = 0.0;
   out_7470146636550372525[269] = 0.0;
   out_7470146636550372525[270] = 0.0;
   out_7470146636550372525[271] = 0.0;
   out_7470146636550372525[272] = 0.0;
   out_7470146636550372525[273] = 0.0;
   out_7470146636550372525[274] = 0.0;
   out_7470146636550372525[275] = 0.0;
   out_7470146636550372525[276] = 0.0;
   out_7470146636550372525[277] = 0.0;
   out_7470146636550372525[278] = 0.0;
   out_7470146636550372525[279] = 0.0;
   out_7470146636550372525[280] = 0.0;
   out_7470146636550372525[281] = 0.0;
   out_7470146636550372525[282] = 0.0;
   out_7470146636550372525[283] = 0.0;
   out_7470146636550372525[284] = 0.0;
   out_7470146636550372525[285] = 1.0;
   out_7470146636550372525[286] = 0.0;
   out_7470146636550372525[287] = 0.0;
   out_7470146636550372525[288] = 0.0;
   out_7470146636550372525[289] = 0.0;
   out_7470146636550372525[290] = 0.0;
   out_7470146636550372525[291] = 0.0;
   out_7470146636550372525[292] = 0.0;
   out_7470146636550372525[293] = 0.0;
   out_7470146636550372525[294] = 0.0;
   out_7470146636550372525[295] = 0.0;
   out_7470146636550372525[296] = 0.0;
   out_7470146636550372525[297] = 0.0;
   out_7470146636550372525[298] = 0.0;
   out_7470146636550372525[299] = 0.0;
   out_7470146636550372525[300] = 0.0;
   out_7470146636550372525[301] = 0.0;
   out_7470146636550372525[302] = 0.0;
   out_7470146636550372525[303] = 0.0;
   out_7470146636550372525[304] = 1.0;
   out_7470146636550372525[305] = 0.0;
   out_7470146636550372525[306] = 0.0;
   out_7470146636550372525[307] = 0.0;
   out_7470146636550372525[308] = 0.0;
   out_7470146636550372525[309] = 0.0;
   out_7470146636550372525[310] = 0.0;
   out_7470146636550372525[311] = 0.0;
   out_7470146636550372525[312] = 0.0;
   out_7470146636550372525[313] = 0.0;
   out_7470146636550372525[314] = 0.0;
   out_7470146636550372525[315] = 0.0;
   out_7470146636550372525[316] = 0.0;
   out_7470146636550372525[317] = 0.0;
   out_7470146636550372525[318] = 0.0;
   out_7470146636550372525[319] = 0.0;
   out_7470146636550372525[320] = 0.0;
   out_7470146636550372525[321] = 0.0;
   out_7470146636550372525[322] = 0.0;
   out_7470146636550372525[323] = 1.0;
}
void f_fun(double *state, double dt, double *out_8463523398219764128) {
   out_8463523398219764128[0] = atan2((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), -(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]));
   out_8463523398219764128[1] = asin(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]));
   out_8463523398219764128[2] = atan2(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), -(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]));
   out_8463523398219764128[3] = dt*state[12] + state[3];
   out_8463523398219764128[4] = dt*state[13] + state[4];
   out_8463523398219764128[5] = dt*state[14] + state[5];
   out_8463523398219764128[6] = state[6];
   out_8463523398219764128[7] = state[7];
   out_8463523398219764128[8] = state[8];
   out_8463523398219764128[9] = state[9];
   out_8463523398219764128[10] = state[10];
   out_8463523398219764128[11] = state[11];
   out_8463523398219764128[12] = state[12];
   out_8463523398219764128[13] = state[13];
   out_8463523398219764128[14] = state[14];
   out_8463523398219764128[15] = state[15];
   out_8463523398219764128[16] = state[16];
   out_8463523398219764128[17] = state[17];
}
void F_fun(double *state, double dt, double *out_3788203468078225680) {
   out_3788203468078225680[0] = ((-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*cos(state[0])*cos(state[1]) - sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*cos(state[0])*cos(state[1]) - sin(dt*state[6])*sin(state[0])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_3788203468078225680[1] = ((-sin(dt*state[6])*sin(dt*state[8]) - sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*cos(state[1]) - (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*sin(state[1]) - sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(state[0]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*sin(state[1]) + (-sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) + sin(dt*state[8])*cos(dt*state[6]))*cos(state[1]) - sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(state[0]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_3788203468078225680[2] = 0;
   out_3788203468078225680[3] = 0;
   out_3788203468078225680[4] = 0;
   out_3788203468078225680[5] = 0;
   out_3788203468078225680[6] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(dt*cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) - dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_3788203468078225680[7] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*sin(dt*state[7])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[6])*sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) - dt*sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[7])*cos(dt*state[6])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[8])*sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]) - dt*sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_3788203468078225680[8] = ((dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((dt*sin(dt*state[6])*sin(dt*state[8]) + dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_3788203468078225680[9] = 0;
   out_3788203468078225680[10] = 0;
   out_3788203468078225680[11] = 0;
   out_3788203468078225680[12] = 0;
   out_3788203468078225680[13] = 0;
   out_3788203468078225680[14] = 0;
   out_3788203468078225680[15] = 0;
   out_3788203468078225680[16] = 0;
   out_3788203468078225680[17] = 0;
   out_3788203468078225680[18] = (-sin(dt*state[7])*sin(state[0])*cos(state[1]) - sin(dt*state[8])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_3788203468078225680[19] = (-sin(dt*state[7])*sin(state[1])*cos(state[0]) + sin(dt*state[8])*sin(state[0])*sin(state[1])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_3788203468078225680[20] = 0;
   out_3788203468078225680[21] = 0;
   out_3788203468078225680[22] = 0;
   out_3788203468078225680[23] = 0;
   out_3788203468078225680[24] = 0;
   out_3788203468078225680[25] = (dt*sin(dt*state[7])*sin(dt*state[8])*sin(state[0])*cos(state[1]) - dt*sin(dt*state[7])*sin(state[1])*cos(dt*state[8]) + dt*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_3788203468078225680[26] = (-dt*sin(dt*state[8])*sin(state[1])*cos(dt*state[7]) - dt*sin(state[0])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_3788203468078225680[27] = 0;
   out_3788203468078225680[28] = 0;
   out_3788203468078225680[29] = 0;
   out_3788203468078225680[30] = 0;
   out_3788203468078225680[31] = 0;
   out_3788203468078225680[32] = 0;
   out_3788203468078225680[33] = 0;
   out_3788203468078225680[34] = 0;
   out_3788203468078225680[35] = 0;
   out_3788203468078225680[36] = ((sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_3788203468078225680[37] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-sin(dt*state[7])*sin(state[2])*cos(state[0])*cos(state[1]) + sin(dt*state[8])*sin(state[0])*sin(state[2])*cos(dt*state[7])*cos(state[1]) - sin(state[1])*sin(state[2])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(-sin(dt*state[7])*cos(state[0])*cos(state[1])*cos(state[2]) + sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1])*cos(state[2]) - sin(state[1])*cos(dt*state[7])*cos(dt*state[8])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_3788203468078225680[38] = ((-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (-sin(state[0])*sin(state[1])*sin(state[2]) - cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_3788203468078225680[39] = 0;
   out_3788203468078225680[40] = 0;
   out_3788203468078225680[41] = 0;
   out_3788203468078225680[42] = 0;
   out_3788203468078225680[43] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(dt*(sin(state[0])*cos(state[2]) - sin(state[1])*sin(state[2])*cos(state[0]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*sin(state[2])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(dt*(-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_3788203468078225680[44] = (dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*sin(state[2])*cos(dt*state[7])*cos(state[1]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + (dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[7])*cos(state[1])*cos(state[2]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_3788203468078225680[45] = 0;
   out_3788203468078225680[46] = 0;
   out_3788203468078225680[47] = 0;
   out_3788203468078225680[48] = 0;
   out_3788203468078225680[49] = 0;
   out_3788203468078225680[50] = 0;
   out_3788203468078225680[51] = 0;
   out_3788203468078225680[52] = 0;
   out_3788203468078225680[53] = 0;
   out_3788203468078225680[54] = 0;
   out_3788203468078225680[55] = 0;
   out_3788203468078225680[56] = 0;
   out_3788203468078225680[57] = 1;
   out_3788203468078225680[58] = 0;
   out_3788203468078225680[59] = 0;
   out_3788203468078225680[60] = 0;
   out_3788203468078225680[61] = 0;
   out_3788203468078225680[62] = 0;
   out_3788203468078225680[63] = 0;
   out_3788203468078225680[64] = 0;
   out_3788203468078225680[65] = 0;
   out_3788203468078225680[66] = dt;
   out_3788203468078225680[67] = 0;
   out_3788203468078225680[68] = 0;
   out_3788203468078225680[69] = 0;
   out_3788203468078225680[70] = 0;
   out_3788203468078225680[71] = 0;
   out_3788203468078225680[72] = 0;
   out_3788203468078225680[73] = 0;
   out_3788203468078225680[74] = 0;
   out_3788203468078225680[75] = 0;
   out_3788203468078225680[76] = 1;
   out_3788203468078225680[77] = 0;
   out_3788203468078225680[78] = 0;
   out_3788203468078225680[79] = 0;
   out_3788203468078225680[80] = 0;
   out_3788203468078225680[81] = 0;
   out_3788203468078225680[82] = 0;
   out_3788203468078225680[83] = 0;
   out_3788203468078225680[84] = 0;
   out_3788203468078225680[85] = dt;
   out_3788203468078225680[86] = 0;
   out_3788203468078225680[87] = 0;
   out_3788203468078225680[88] = 0;
   out_3788203468078225680[89] = 0;
   out_3788203468078225680[90] = 0;
   out_3788203468078225680[91] = 0;
   out_3788203468078225680[92] = 0;
   out_3788203468078225680[93] = 0;
   out_3788203468078225680[94] = 0;
   out_3788203468078225680[95] = 1;
   out_3788203468078225680[96] = 0;
   out_3788203468078225680[97] = 0;
   out_3788203468078225680[98] = 0;
   out_3788203468078225680[99] = 0;
   out_3788203468078225680[100] = 0;
   out_3788203468078225680[101] = 0;
   out_3788203468078225680[102] = 0;
   out_3788203468078225680[103] = 0;
   out_3788203468078225680[104] = dt;
   out_3788203468078225680[105] = 0;
   out_3788203468078225680[106] = 0;
   out_3788203468078225680[107] = 0;
   out_3788203468078225680[108] = 0;
   out_3788203468078225680[109] = 0;
   out_3788203468078225680[110] = 0;
   out_3788203468078225680[111] = 0;
   out_3788203468078225680[112] = 0;
   out_3788203468078225680[113] = 0;
   out_3788203468078225680[114] = 1;
   out_3788203468078225680[115] = 0;
   out_3788203468078225680[116] = 0;
   out_3788203468078225680[117] = 0;
   out_3788203468078225680[118] = 0;
   out_3788203468078225680[119] = 0;
   out_3788203468078225680[120] = 0;
   out_3788203468078225680[121] = 0;
   out_3788203468078225680[122] = 0;
   out_3788203468078225680[123] = 0;
   out_3788203468078225680[124] = 0;
   out_3788203468078225680[125] = 0;
   out_3788203468078225680[126] = 0;
   out_3788203468078225680[127] = 0;
   out_3788203468078225680[128] = 0;
   out_3788203468078225680[129] = 0;
   out_3788203468078225680[130] = 0;
   out_3788203468078225680[131] = 0;
   out_3788203468078225680[132] = 0;
   out_3788203468078225680[133] = 1;
   out_3788203468078225680[134] = 0;
   out_3788203468078225680[135] = 0;
   out_3788203468078225680[136] = 0;
   out_3788203468078225680[137] = 0;
   out_3788203468078225680[138] = 0;
   out_3788203468078225680[139] = 0;
   out_3788203468078225680[140] = 0;
   out_3788203468078225680[141] = 0;
   out_3788203468078225680[142] = 0;
   out_3788203468078225680[143] = 0;
   out_3788203468078225680[144] = 0;
   out_3788203468078225680[145] = 0;
   out_3788203468078225680[146] = 0;
   out_3788203468078225680[147] = 0;
   out_3788203468078225680[148] = 0;
   out_3788203468078225680[149] = 0;
   out_3788203468078225680[150] = 0;
   out_3788203468078225680[151] = 0;
   out_3788203468078225680[152] = 1;
   out_3788203468078225680[153] = 0;
   out_3788203468078225680[154] = 0;
   out_3788203468078225680[155] = 0;
   out_3788203468078225680[156] = 0;
   out_3788203468078225680[157] = 0;
   out_3788203468078225680[158] = 0;
   out_3788203468078225680[159] = 0;
   out_3788203468078225680[160] = 0;
   out_3788203468078225680[161] = 0;
   out_3788203468078225680[162] = 0;
   out_3788203468078225680[163] = 0;
   out_3788203468078225680[164] = 0;
   out_3788203468078225680[165] = 0;
   out_3788203468078225680[166] = 0;
   out_3788203468078225680[167] = 0;
   out_3788203468078225680[168] = 0;
   out_3788203468078225680[169] = 0;
   out_3788203468078225680[170] = 0;
   out_3788203468078225680[171] = 1;
   out_3788203468078225680[172] = 0;
   out_3788203468078225680[173] = 0;
   out_3788203468078225680[174] = 0;
   out_3788203468078225680[175] = 0;
   out_3788203468078225680[176] = 0;
   out_3788203468078225680[177] = 0;
   out_3788203468078225680[178] = 0;
   out_3788203468078225680[179] = 0;
   out_3788203468078225680[180] = 0;
   out_3788203468078225680[181] = 0;
   out_3788203468078225680[182] = 0;
   out_3788203468078225680[183] = 0;
   out_3788203468078225680[184] = 0;
   out_3788203468078225680[185] = 0;
   out_3788203468078225680[186] = 0;
   out_3788203468078225680[187] = 0;
   out_3788203468078225680[188] = 0;
   out_3788203468078225680[189] = 0;
   out_3788203468078225680[190] = 1;
   out_3788203468078225680[191] = 0;
   out_3788203468078225680[192] = 0;
   out_3788203468078225680[193] = 0;
   out_3788203468078225680[194] = 0;
   out_3788203468078225680[195] = 0;
   out_3788203468078225680[196] = 0;
   out_3788203468078225680[197] = 0;
   out_3788203468078225680[198] = 0;
   out_3788203468078225680[199] = 0;
   out_3788203468078225680[200] = 0;
   out_3788203468078225680[201] = 0;
   out_3788203468078225680[202] = 0;
   out_3788203468078225680[203] = 0;
   out_3788203468078225680[204] = 0;
   out_3788203468078225680[205] = 0;
   out_3788203468078225680[206] = 0;
   out_3788203468078225680[207] = 0;
   out_3788203468078225680[208] = 0;
   out_3788203468078225680[209] = 1;
   out_3788203468078225680[210] = 0;
   out_3788203468078225680[211] = 0;
   out_3788203468078225680[212] = 0;
   out_3788203468078225680[213] = 0;
   out_3788203468078225680[214] = 0;
   out_3788203468078225680[215] = 0;
   out_3788203468078225680[216] = 0;
   out_3788203468078225680[217] = 0;
   out_3788203468078225680[218] = 0;
   out_3788203468078225680[219] = 0;
   out_3788203468078225680[220] = 0;
   out_3788203468078225680[221] = 0;
   out_3788203468078225680[222] = 0;
   out_3788203468078225680[223] = 0;
   out_3788203468078225680[224] = 0;
   out_3788203468078225680[225] = 0;
   out_3788203468078225680[226] = 0;
   out_3788203468078225680[227] = 0;
   out_3788203468078225680[228] = 1;
   out_3788203468078225680[229] = 0;
   out_3788203468078225680[230] = 0;
   out_3788203468078225680[231] = 0;
   out_3788203468078225680[232] = 0;
   out_3788203468078225680[233] = 0;
   out_3788203468078225680[234] = 0;
   out_3788203468078225680[235] = 0;
   out_3788203468078225680[236] = 0;
   out_3788203468078225680[237] = 0;
   out_3788203468078225680[238] = 0;
   out_3788203468078225680[239] = 0;
   out_3788203468078225680[240] = 0;
   out_3788203468078225680[241] = 0;
   out_3788203468078225680[242] = 0;
   out_3788203468078225680[243] = 0;
   out_3788203468078225680[244] = 0;
   out_3788203468078225680[245] = 0;
   out_3788203468078225680[246] = 0;
   out_3788203468078225680[247] = 1;
   out_3788203468078225680[248] = 0;
   out_3788203468078225680[249] = 0;
   out_3788203468078225680[250] = 0;
   out_3788203468078225680[251] = 0;
   out_3788203468078225680[252] = 0;
   out_3788203468078225680[253] = 0;
   out_3788203468078225680[254] = 0;
   out_3788203468078225680[255] = 0;
   out_3788203468078225680[256] = 0;
   out_3788203468078225680[257] = 0;
   out_3788203468078225680[258] = 0;
   out_3788203468078225680[259] = 0;
   out_3788203468078225680[260] = 0;
   out_3788203468078225680[261] = 0;
   out_3788203468078225680[262] = 0;
   out_3788203468078225680[263] = 0;
   out_3788203468078225680[264] = 0;
   out_3788203468078225680[265] = 0;
   out_3788203468078225680[266] = 1;
   out_3788203468078225680[267] = 0;
   out_3788203468078225680[268] = 0;
   out_3788203468078225680[269] = 0;
   out_3788203468078225680[270] = 0;
   out_3788203468078225680[271] = 0;
   out_3788203468078225680[272] = 0;
   out_3788203468078225680[273] = 0;
   out_3788203468078225680[274] = 0;
   out_3788203468078225680[275] = 0;
   out_3788203468078225680[276] = 0;
   out_3788203468078225680[277] = 0;
   out_3788203468078225680[278] = 0;
   out_3788203468078225680[279] = 0;
   out_3788203468078225680[280] = 0;
   out_3788203468078225680[281] = 0;
   out_3788203468078225680[282] = 0;
   out_3788203468078225680[283] = 0;
   out_3788203468078225680[284] = 0;
   out_3788203468078225680[285] = 1;
   out_3788203468078225680[286] = 0;
   out_3788203468078225680[287] = 0;
   out_3788203468078225680[288] = 0;
   out_3788203468078225680[289] = 0;
   out_3788203468078225680[290] = 0;
   out_3788203468078225680[291] = 0;
   out_3788203468078225680[292] = 0;
   out_3788203468078225680[293] = 0;
   out_3788203468078225680[294] = 0;
   out_3788203468078225680[295] = 0;
   out_3788203468078225680[296] = 0;
   out_3788203468078225680[297] = 0;
   out_3788203468078225680[298] = 0;
   out_3788203468078225680[299] = 0;
   out_3788203468078225680[300] = 0;
   out_3788203468078225680[301] = 0;
   out_3788203468078225680[302] = 0;
   out_3788203468078225680[303] = 0;
   out_3788203468078225680[304] = 1;
   out_3788203468078225680[305] = 0;
   out_3788203468078225680[306] = 0;
   out_3788203468078225680[307] = 0;
   out_3788203468078225680[308] = 0;
   out_3788203468078225680[309] = 0;
   out_3788203468078225680[310] = 0;
   out_3788203468078225680[311] = 0;
   out_3788203468078225680[312] = 0;
   out_3788203468078225680[313] = 0;
   out_3788203468078225680[314] = 0;
   out_3788203468078225680[315] = 0;
   out_3788203468078225680[316] = 0;
   out_3788203468078225680[317] = 0;
   out_3788203468078225680[318] = 0;
   out_3788203468078225680[319] = 0;
   out_3788203468078225680[320] = 0;
   out_3788203468078225680[321] = 0;
   out_3788203468078225680[322] = 0;
   out_3788203468078225680[323] = 1;
}
void h_4(double *state, double *unused, double *out_5084485555257631001) {
   out_5084485555257631001[0] = state[6] + state[9];
   out_5084485555257631001[1] = state[7] + state[10];
   out_5084485555257631001[2] = state[8] + state[11];
}
void H_4(double *state, double *unused, double *out_7702375358368229838) {
   out_7702375358368229838[0] = 0;
   out_7702375358368229838[1] = 0;
   out_7702375358368229838[2] = 0;
   out_7702375358368229838[3] = 0;
   out_7702375358368229838[4] = 0;
   out_7702375358368229838[5] = 0;
   out_7702375358368229838[6] = 1;
   out_7702375358368229838[7] = 0;
   out_7702375358368229838[8] = 0;
   out_7702375358368229838[9] = 1;
   out_7702375358368229838[10] = 0;
   out_7702375358368229838[11] = 0;
   out_7702375358368229838[12] = 0;
   out_7702375358368229838[13] = 0;
   out_7702375358368229838[14] = 0;
   out_7702375358368229838[15] = 0;
   out_7702375358368229838[16] = 0;
   out_7702375358368229838[17] = 0;
   out_7702375358368229838[18] = 0;
   out_7702375358368229838[19] = 0;
   out_7702375358368229838[20] = 0;
   out_7702375358368229838[21] = 0;
   out_7702375358368229838[22] = 0;
   out_7702375358368229838[23] = 0;
   out_7702375358368229838[24] = 0;
   out_7702375358368229838[25] = 1;
   out_7702375358368229838[26] = 0;
   out_7702375358368229838[27] = 0;
   out_7702375358368229838[28] = 1;
   out_7702375358368229838[29] = 0;
   out_7702375358368229838[30] = 0;
   out_7702375358368229838[31] = 0;
   out_7702375358368229838[32] = 0;
   out_7702375358368229838[33] = 0;
   out_7702375358368229838[34] = 0;
   out_7702375358368229838[35] = 0;
   out_7702375358368229838[36] = 0;
   out_7702375358368229838[37] = 0;
   out_7702375358368229838[38] = 0;
   out_7702375358368229838[39] = 0;
   out_7702375358368229838[40] = 0;
   out_7702375358368229838[41] = 0;
   out_7702375358368229838[42] = 0;
   out_7702375358368229838[43] = 0;
   out_7702375358368229838[44] = 1;
   out_7702375358368229838[45] = 0;
   out_7702375358368229838[46] = 0;
   out_7702375358368229838[47] = 1;
   out_7702375358368229838[48] = 0;
   out_7702375358368229838[49] = 0;
   out_7702375358368229838[50] = 0;
   out_7702375358368229838[51] = 0;
   out_7702375358368229838[52] = 0;
   out_7702375358368229838[53] = 0;
}
void h_10(double *state, double *unused, double *out_2120190459475098069) {
   out_2120190459475098069[0] = 9.8100000000000005*sin(state[1]) - state[4]*state[8] + state[5]*state[7] + state[12] + state[15];
   out_2120190459475098069[1] = -9.8100000000000005*sin(state[0])*cos(state[1]) + state[3]*state[8] - state[5]*state[6] + state[13] + state[16];
   out_2120190459475098069[2] = -9.8100000000000005*cos(state[0])*cos(state[1]) - state[3]*state[7] + state[4]*state[6] + state[14] + state[17];
}
void H_10(double *state, double *unused, double *out_2259294001395867057) {
   out_2259294001395867057[0] = 0;
   out_2259294001395867057[1] = 9.8100000000000005*cos(state[1]);
   out_2259294001395867057[2] = 0;
   out_2259294001395867057[3] = 0;
   out_2259294001395867057[4] = -state[8];
   out_2259294001395867057[5] = state[7];
   out_2259294001395867057[6] = 0;
   out_2259294001395867057[7] = state[5];
   out_2259294001395867057[8] = -state[4];
   out_2259294001395867057[9] = 0;
   out_2259294001395867057[10] = 0;
   out_2259294001395867057[11] = 0;
   out_2259294001395867057[12] = 1;
   out_2259294001395867057[13] = 0;
   out_2259294001395867057[14] = 0;
   out_2259294001395867057[15] = 1;
   out_2259294001395867057[16] = 0;
   out_2259294001395867057[17] = 0;
   out_2259294001395867057[18] = -9.8100000000000005*cos(state[0])*cos(state[1]);
   out_2259294001395867057[19] = 9.8100000000000005*sin(state[0])*sin(state[1]);
   out_2259294001395867057[20] = 0;
   out_2259294001395867057[21] = state[8];
   out_2259294001395867057[22] = 0;
   out_2259294001395867057[23] = -state[6];
   out_2259294001395867057[24] = -state[5];
   out_2259294001395867057[25] = 0;
   out_2259294001395867057[26] = state[3];
   out_2259294001395867057[27] = 0;
   out_2259294001395867057[28] = 0;
   out_2259294001395867057[29] = 0;
   out_2259294001395867057[30] = 0;
   out_2259294001395867057[31] = 1;
   out_2259294001395867057[32] = 0;
   out_2259294001395867057[33] = 0;
   out_2259294001395867057[34] = 1;
   out_2259294001395867057[35] = 0;
   out_2259294001395867057[36] = 9.8100000000000005*sin(state[0])*cos(state[1]);
   out_2259294001395867057[37] = 9.8100000000000005*sin(state[1])*cos(state[0]);
   out_2259294001395867057[38] = 0;
   out_2259294001395867057[39] = -state[7];
   out_2259294001395867057[40] = state[6];
   out_2259294001395867057[41] = 0;
   out_2259294001395867057[42] = state[4];
   out_2259294001395867057[43] = -state[3];
   out_2259294001395867057[44] = 0;
   out_2259294001395867057[45] = 0;
   out_2259294001395867057[46] = 0;
   out_2259294001395867057[47] = 0;
   out_2259294001395867057[48] = 0;
   out_2259294001395867057[49] = 0;
   out_2259294001395867057[50] = 1;
   out_2259294001395867057[51] = 0;
   out_2259294001395867057[52] = 0;
   out_2259294001395867057[53] = 1;
}
void h_13(double *state, double *unused, double *out_5269954238728557064) {
   out_5269954238728557064[0] = state[3];
   out_5269954238728557064[1] = state[4];
   out_5269954238728557064[2] = state[5];
}
void H_13(double *state, double *unused, double *out_7532094890008988977) {
   out_7532094890008988977[0] = 0;
   out_7532094890008988977[1] = 0;
   out_7532094890008988977[2] = 0;
   out_7532094890008988977[3] = 1;
   out_7532094890008988977[4] = 0;
   out_7532094890008988977[5] = 0;
   out_7532094890008988977[6] = 0;
   out_7532094890008988977[7] = 0;
   out_7532094890008988977[8] = 0;
   out_7532094890008988977[9] = 0;
   out_7532094890008988977[10] = 0;
   out_7532094890008988977[11] = 0;
   out_7532094890008988977[12] = 0;
   out_7532094890008988977[13] = 0;
   out_7532094890008988977[14] = 0;
   out_7532094890008988977[15] = 0;
   out_7532094890008988977[16] = 0;
   out_7532094890008988977[17] = 0;
   out_7532094890008988977[18] = 0;
   out_7532094890008988977[19] = 0;
   out_7532094890008988977[20] = 0;
   out_7532094890008988977[21] = 0;
   out_7532094890008988977[22] = 1;
   out_7532094890008988977[23] = 0;
   out_7532094890008988977[24] = 0;
   out_7532094890008988977[25] = 0;
   out_7532094890008988977[26] = 0;
   out_7532094890008988977[27] = 0;
   out_7532094890008988977[28] = 0;
   out_7532094890008988977[29] = 0;
   out_7532094890008988977[30] = 0;
   out_7532094890008988977[31] = 0;
   out_7532094890008988977[32] = 0;
   out_7532094890008988977[33] = 0;
   out_7532094890008988977[34] = 0;
   out_7532094890008988977[35] = 0;
   out_7532094890008988977[36] = 0;
   out_7532094890008988977[37] = 0;
   out_7532094890008988977[38] = 0;
   out_7532094890008988977[39] = 0;
   out_7532094890008988977[40] = 0;
   out_7532094890008988977[41] = 1;
   out_7532094890008988977[42] = 0;
   out_7532094890008988977[43] = 0;
   out_7532094890008988977[44] = 0;
   out_7532094890008988977[45] = 0;
   out_7532094890008988977[46] = 0;
   out_7532094890008988977[47] = 0;
   out_7532094890008988977[48] = 0;
   out_7532094890008988977[49] = 0;
   out_7532094890008988977[50] = 0;
   out_7532094890008988977[51] = 0;
   out_7532094890008988977[52] = 0;
   out_7532094890008988977[53] = 0;
}
void h_14(double *state, double *unused, double *out_8523036253873003715) {
   out_8523036253873003715[0] = state[6];
   out_8523036253873003715[1] = state[7];
   out_8523036253873003715[2] = state[8];
}
void H_14(double *state, double *unused, double *out_6781127859001837249) {
   out_6781127859001837249[0] = 0;
   out_6781127859001837249[1] = 0;
   out_6781127859001837249[2] = 0;
   out_6781127859001837249[3] = 0;
   out_6781127859001837249[4] = 0;
   out_6781127859001837249[5] = 0;
   out_6781127859001837249[6] = 1;
   out_6781127859001837249[7] = 0;
   out_6781127859001837249[8] = 0;
   out_6781127859001837249[9] = 0;
   out_6781127859001837249[10] = 0;
   out_6781127859001837249[11] = 0;
   out_6781127859001837249[12] = 0;
   out_6781127859001837249[13] = 0;
   out_6781127859001837249[14] = 0;
   out_6781127859001837249[15] = 0;
   out_6781127859001837249[16] = 0;
   out_6781127859001837249[17] = 0;
   out_6781127859001837249[18] = 0;
   out_6781127859001837249[19] = 0;
   out_6781127859001837249[20] = 0;
   out_6781127859001837249[21] = 0;
   out_6781127859001837249[22] = 0;
   out_6781127859001837249[23] = 0;
   out_6781127859001837249[24] = 0;
   out_6781127859001837249[25] = 1;
   out_6781127859001837249[26] = 0;
   out_6781127859001837249[27] = 0;
   out_6781127859001837249[28] = 0;
   out_6781127859001837249[29] = 0;
   out_6781127859001837249[30] = 0;
   out_6781127859001837249[31] = 0;
   out_6781127859001837249[32] = 0;
   out_6781127859001837249[33] = 0;
   out_6781127859001837249[34] = 0;
   out_6781127859001837249[35] = 0;
   out_6781127859001837249[36] = 0;
   out_6781127859001837249[37] = 0;
   out_6781127859001837249[38] = 0;
   out_6781127859001837249[39] = 0;
   out_6781127859001837249[40] = 0;
   out_6781127859001837249[41] = 0;
   out_6781127859001837249[42] = 0;
   out_6781127859001837249[43] = 0;
   out_6781127859001837249[44] = 1;
   out_6781127859001837249[45] = 0;
   out_6781127859001837249[46] = 0;
   out_6781127859001837249[47] = 0;
   out_6781127859001837249[48] = 0;
   out_6781127859001837249[49] = 0;
   out_6781127859001837249[50] = 0;
   out_6781127859001837249[51] = 0;
   out_6781127859001837249[52] = 0;
   out_6781127859001837249[53] = 0;
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

void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_4, H_4, NULL, in_z, in_R, in_ea, MAHA_THRESH_4);
}
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_10, H_10, NULL, in_z, in_R, in_ea, MAHA_THRESH_10);
}
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_13, H_13, NULL, in_z, in_R, in_ea, MAHA_THRESH_13);
}
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_14, H_14, NULL, in_z, in_R, in_ea, MAHA_THRESH_14);
}
void pose_err_fun(double *nom_x, double *delta_x, double *out_3159499921099066449) {
  err_fun(nom_x, delta_x, out_3159499921099066449);
}
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_6765203926591570612) {
  inv_err_fun(nom_x, true_x, out_6765203926591570612);
}
void pose_H_mod_fun(double *state, double *out_7470146636550372525) {
  H_mod_fun(state, out_7470146636550372525);
}
void pose_f_fun(double *state, double dt, double *out_8463523398219764128) {
  f_fun(state,  dt, out_8463523398219764128);
}
void pose_F_fun(double *state, double dt, double *out_3788203468078225680) {
  F_fun(state,  dt, out_3788203468078225680);
}
void pose_h_4(double *state, double *unused, double *out_5084485555257631001) {
  h_4(state, unused, out_5084485555257631001);
}
void pose_H_4(double *state, double *unused, double *out_7702375358368229838) {
  H_4(state, unused, out_7702375358368229838);
}
void pose_h_10(double *state, double *unused, double *out_2120190459475098069) {
  h_10(state, unused, out_2120190459475098069);
}
void pose_H_10(double *state, double *unused, double *out_2259294001395867057) {
  H_10(state, unused, out_2259294001395867057);
}
void pose_h_13(double *state, double *unused, double *out_5269954238728557064) {
  h_13(state, unused, out_5269954238728557064);
}
void pose_H_13(double *state, double *unused, double *out_7532094890008988977) {
  H_13(state, unused, out_7532094890008988977);
}
void pose_h_14(double *state, double *unused, double *out_8523036253873003715) {
  h_14(state, unused, out_8523036253873003715);
}
void pose_H_14(double *state, double *unused, double *out_6781127859001837249) {
  H_14(state, unused, out_6781127859001837249);
}
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
}

const EKF pose = {
  .name = "pose",
  .kinds = { 4, 10, 13, 14 },
  .feature_kinds = {  },
  .f_fun = pose_f_fun,
  .F_fun = pose_F_fun,
  .err_fun = pose_err_fun,
  .inv_err_fun = pose_inv_err_fun,
  .H_mod_fun = pose_H_mod_fun,
  .predict = pose_predict,
  .hs = {
    { 4, pose_h_4 },
    { 10, pose_h_10 },
    { 13, pose_h_13 },
    { 14, pose_h_14 },
  },
  .Hs = {
    { 4, pose_H_4 },
    { 10, pose_H_10 },
    { 13, pose_H_13 },
    { 14, pose_H_14 },
  },
  .updates = {
    { 4, pose_update_4 },
    { 10, pose_update_10 },
    { 13, pose_update_13 },
    { 14, pose_update_14 },
  },
  .Hes = {
  },
  .sets = {
  },
  .extra_routines = {
  },
};

ekf_lib_init(pose)
