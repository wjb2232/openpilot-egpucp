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
void err_fun(double *nom_x, double *delta_x, double *out_431546898630699983) {
   out_431546898630699983[0] = delta_x[0] + nom_x[0];
   out_431546898630699983[1] = delta_x[1] + nom_x[1];
   out_431546898630699983[2] = delta_x[2] + nom_x[2];
   out_431546898630699983[3] = delta_x[3] + nom_x[3];
   out_431546898630699983[4] = delta_x[4] + nom_x[4];
   out_431546898630699983[5] = delta_x[5] + nom_x[5];
   out_431546898630699983[6] = delta_x[6] + nom_x[6];
   out_431546898630699983[7] = delta_x[7] + nom_x[7];
   out_431546898630699983[8] = delta_x[8] + nom_x[8];
   out_431546898630699983[9] = delta_x[9] + nom_x[9];
   out_431546898630699983[10] = delta_x[10] + nom_x[10];
   out_431546898630699983[11] = delta_x[11] + nom_x[11];
   out_431546898630699983[12] = delta_x[12] + nom_x[12];
   out_431546898630699983[13] = delta_x[13] + nom_x[13];
   out_431546898630699983[14] = delta_x[14] + nom_x[14];
   out_431546898630699983[15] = delta_x[15] + nom_x[15];
   out_431546898630699983[16] = delta_x[16] + nom_x[16];
   out_431546898630699983[17] = delta_x[17] + nom_x[17];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_3139108192969388081) {
   out_3139108192969388081[0] = -nom_x[0] + true_x[0];
   out_3139108192969388081[1] = -nom_x[1] + true_x[1];
   out_3139108192969388081[2] = -nom_x[2] + true_x[2];
   out_3139108192969388081[3] = -nom_x[3] + true_x[3];
   out_3139108192969388081[4] = -nom_x[4] + true_x[4];
   out_3139108192969388081[5] = -nom_x[5] + true_x[5];
   out_3139108192969388081[6] = -nom_x[6] + true_x[6];
   out_3139108192969388081[7] = -nom_x[7] + true_x[7];
   out_3139108192969388081[8] = -nom_x[8] + true_x[8];
   out_3139108192969388081[9] = -nom_x[9] + true_x[9];
   out_3139108192969388081[10] = -nom_x[10] + true_x[10];
   out_3139108192969388081[11] = -nom_x[11] + true_x[11];
   out_3139108192969388081[12] = -nom_x[12] + true_x[12];
   out_3139108192969388081[13] = -nom_x[13] + true_x[13];
   out_3139108192969388081[14] = -nom_x[14] + true_x[14];
   out_3139108192969388081[15] = -nom_x[15] + true_x[15];
   out_3139108192969388081[16] = -nom_x[16] + true_x[16];
   out_3139108192969388081[17] = -nom_x[17] + true_x[17];
}
void H_mod_fun(double *state, double *out_2571791232745662537) {
   out_2571791232745662537[0] = 1.0;
   out_2571791232745662537[1] = 0.0;
   out_2571791232745662537[2] = 0.0;
   out_2571791232745662537[3] = 0.0;
   out_2571791232745662537[4] = 0.0;
   out_2571791232745662537[5] = 0.0;
   out_2571791232745662537[6] = 0.0;
   out_2571791232745662537[7] = 0.0;
   out_2571791232745662537[8] = 0.0;
   out_2571791232745662537[9] = 0.0;
   out_2571791232745662537[10] = 0.0;
   out_2571791232745662537[11] = 0.0;
   out_2571791232745662537[12] = 0.0;
   out_2571791232745662537[13] = 0.0;
   out_2571791232745662537[14] = 0.0;
   out_2571791232745662537[15] = 0.0;
   out_2571791232745662537[16] = 0.0;
   out_2571791232745662537[17] = 0.0;
   out_2571791232745662537[18] = 0.0;
   out_2571791232745662537[19] = 1.0;
   out_2571791232745662537[20] = 0.0;
   out_2571791232745662537[21] = 0.0;
   out_2571791232745662537[22] = 0.0;
   out_2571791232745662537[23] = 0.0;
   out_2571791232745662537[24] = 0.0;
   out_2571791232745662537[25] = 0.0;
   out_2571791232745662537[26] = 0.0;
   out_2571791232745662537[27] = 0.0;
   out_2571791232745662537[28] = 0.0;
   out_2571791232745662537[29] = 0.0;
   out_2571791232745662537[30] = 0.0;
   out_2571791232745662537[31] = 0.0;
   out_2571791232745662537[32] = 0.0;
   out_2571791232745662537[33] = 0.0;
   out_2571791232745662537[34] = 0.0;
   out_2571791232745662537[35] = 0.0;
   out_2571791232745662537[36] = 0.0;
   out_2571791232745662537[37] = 0.0;
   out_2571791232745662537[38] = 1.0;
   out_2571791232745662537[39] = 0.0;
   out_2571791232745662537[40] = 0.0;
   out_2571791232745662537[41] = 0.0;
   out_2571791232745662537[42] = 0.0;
   out_2571791232745662537[43] = 0.0;
   out_2571791232745662537[44] = 0.0;
   out_2571791232745662537[45] = 0.0;
   out_2571791232745662537[46] = 0.0;
   out_2571791232745662537[47] = 0.0;
   out_2571791232745662537[48] = 0.0;
   out_2571791232745662537[49] = 0.0;
   out_2571791232745662537[50] = 0.0;
   out_2571791232745662537[51] = 0.0;
   out_2571791232745662537[52] = 0.0;
   out_2571791232745662537[53] = 0.0;
   out_2571791232745662537[54] = 0.0;
   out_2571791232745662537[55] = 0.0;
   out_2571791232745662537[56] = 0.0;
   out_2571791232745662537[57] = 1.0;
   out_2571791232745662537[58] = 0.0;
   out_2571791232745662537[59] = 0.0;
   out_2571791232745662537[60] = 0.0;
   out_2571791232745662537[61] = 0.0;
   out_2571791232745662537[62] = 0.0;
   out_2571791232745662537[63] = 0.0;
   out_2571791232745662537[64] = 0.0;
   out_2571791232745662537[65] = 0.0;
   out_2571791232745662537[66] = 0.0;
   out_2571791232745662537[67] = 0.0;
   out_2571791232745662537[68] = 0.0;
   out_2571791232745662537[69] = 0.0;
   out_2571791232745662537[70] = 0.0;
   out_2571791232745662537[71] = 0.0;
   out_2571791232745662537[72] = 0.0;
   out_2571791232745662537[73] = 0.0;
   out_2571791232745662537[74] = 0.0;
   out_2571791232745662537[75] = 0.0;
   out_2571791232745662537[76] = 1.0;
   out_2571791232745662537[77] = 0.0;
   out_2571791232745662537[78] = 0.0;
   out_2571791232745662537[79] = 0.0;
   out_2571791232745662537[80] = 0.0;
   out_2571791232745662537[81] = 0.0;
   out_2571791232745662537[82] = 0.0;
   out_2571791232745662537[83] = 0.0;
   out_2571791232745662537[84] = 0.0;
   out_2571791232745662537[85] = 0.0;
   out_2571791232745662537[86] = 0.0;
   out_2571791232745662537[87] = 0.0;
   out_2571791232745662537[88] = 0.0;
   out_2571791232745662537[89] = 0.0;
   out_2571791232745662537[90] = 0.0;
   out_2571791232745662537[91] = 0.0;
   out_2571791232745662537[92] = 0.0;
   out_2571791232745662537[93] = 0.0;
   out_2571791232745662537[94] = 0.0;
   out_2571791232745662537[95] = 1.0;
   out_2571791232745662537[96] = 0.0;
   out_2571791232745662537[97] = 0.0;
   out_2571791232745662537[98] = 0.0;
   out_2571791232745662537[99] = 0.0;
   out_2571791232745662537[100] = 0.0;
   out_2571791232745662537[101] = 0.0;
   out_2571791232745662537[102] = 0.0;
   out_2571791232745662537[103] = 0.0;
   out_2571791232745662537[104] = 0.0;
   out_2571791232745662537[105] = 0.0;
   out_2571791232745662537[106] = 0.0;
   out_2571791232745662537[107] = 0.0;
   out_2571791232745662537[108] = 0.0;
   out_2571791232745662537[109] = 0.0;
   out_2571791232745662537[110] = 0.0;
   out_2571791232745662537[111] = 0.0;
   out_2571791232745662537[112] = 0.0;
   out_2571791232745662537[113] = 0.0;
   out_2571791232745662537[114] = 1.0;
   out_2571791232745662537[115] = 0.0;
   out_2571791232745662537[116] = 0.0;
   out_2571791232745662537[117] = 0.0;
   out_2571791232745662537[118] = 0.0;
   out_2571791232745662537[119] = 0.0;
   out_2571791232745662537[120] = 0.0;
   out_2571791232745662537[121] = 0.0;
   out_2571791232745662537[122] = 0.0;
   out_2571791232745662537[123] = 0.0;
   out_2571791232745662537[124] = 0.0;
   out_2571791232745662537[125] = 0.0;
   out_2571791232745662537[126] = 0.0;
   out_2571791232745662537[127] = 0.0;
   out_2571791232745662537[128] = 0.0;
   out_2571791232745662537[129] = 0.0;
   out_2571791232745662537[130] = 0.0;
   out_2571791232745662537[131] = 0.0;
   out_2571791232745662537[132] = 0.0;
   out_2571791232745662537[133] = 1.0;
   out_2571791232745662537[134] = 0.0;
   out_2571791232745662537[135] = 0.0;
   out_2571791232745662537[136] = 0.0;
   out_2571791232745662537[137] = 0.0;
   out_2571791232745662537[138] = 0.0;
   out_2571791232745662537[139] = 0.0;
   out_2571791232745662537[140] = 0.0;
   out_2571791232745662537[141] = 0.0;
   out_2571791232745662537[142] = 0.0;
   out_2571791232745662537[143] = 0.0;
   out_2571791232745662537[144] = 0.0;
   out_2571791232745662537[145] = 0.0;
   out_2571791232745662537[146] = 0.0;
   out_2571791232745662537[147] = 0.0;
   out_2571791232745662537[148] = 0.0;
   out_2571791232745662537[149] = 0.0;
   out_2571791232745662537[150] = 0.0;
   out_2571791232745662537[151] = 0.0;
   out_2571791232745662537[152] = 1.0;
   out_2571791232745662537[153] = 0.0;
   out_2571791232745662537[154] = 0.0;
   out_2571791232745662537[155] = 0.0;
   out_2571791232745662537[156] = 0.0;
   out_2571791232745662537[157] = 0.0;
   out_2571791232745662537[158] = 0.0;
   out_2571791232745662537[159] = 0.0;
   out_2571791232745662537[160] = 0.0;
   out_2571791232745662537[161] = 0.0;
   out_2571791232745662537[162] = 0.0;
   out_2571791232745662537[163] = 0.0;
   out_2571791232745662537[164] = 0.0;
   out_2571791232745662537[165] = 0.0;
   out_2571791232745662537[166] = 0.0;
   out_2571791232745662537[167] = 0.0;
   out_2571791232745662537[168] = 0.0;
   out_2571791232745662537[169] = 0.0;
   out_2571791232745662537[170] = 0.0;
   out_2571791232745662537[171] = 1.0;
   out_2571791232745662537[172] = 0.0;
   out_2571791232745662537[173] = 0.0;
   out_2571791232745662537[174] = 0.0;
   out_2571791232745662537[175] = 0.0;
   out_2571791232745662537[176] = 0.0;
   out_2571791232745662537[177] = 0.0;
   out_2571791232745662537[178] = 0.0;
   out_2571791232745662537[179] = 0.0;
   out_2571791232745662537[180] = 0.0;
   out_2571791232745662537[181] = 0.0;
   out_2571791232745662537[182] = 0.0;
   out_2571791232745662537[183] = 0.0;
   out_2571791232745662537[184] = 0.0;
   out_2571791232745662537[185] = 0.0;
   out_2571791232745662537[186] = 0.0;
   out_2571791232745662537[187] = 0.0;
   out_2571791232745662537[188] = 0.0;
   out_2571791232745662537[189] = 0.0;
   out_2571791232745662537[190] = 1.0;
   out_2571791232745662537[191] = 0.0;
   out_2571791232745662537[192] = 0.0;
   out_2571791232745662537[193] = 0.0;
   out_2571791232745662537[194] = 0.0;
   out_2571791232745662537[195] = 0.0;
   out_2571791232745662537[196] = 0.0;
   out_2571791232745662537[197] = 0.0;
   out_2571791232745662537[198] = 0.0;
   out_2571791232745662537[199] = 0.0;
   out_2571791232745662537[200] = 0.0;
   out_2571791232745662537[201] = 0.0;
   out_2571791232745662537[202] = 0.0;
   out_2571791232745662537[203] = 0.0;
   out_2571791232745662537[204] = 0.0;
   out_2571791232745662537[205] = 0.0;
   out_2571791232745662537[206] = 0.0;
   out_2571791232745662537[207] = 0.0;
   out_2571791232745662537[208] = 0.0;
   out_2571791232745662537[209] = 1.0;
   out_2571791232745662537[210] = 0.0;
   out_2571791232745662537[211] = 0.0;
   out_2571791232745662537[212] = 0.0;
   out_2571791232745662537[213] = 0.0;
   out_2571791232745662537[214] = 0.0;
   out_2571791232745662537[215] = 0.0;
   out_2571791232745662537[216] = 0.0;
   out_2571791232745662537[217] = 0.0;
   out_2571791232745662537[218] = 0.0;
   out_2571791232745662537[219] = 0.0;
   out_2571791232745662537[220] = 0.0;
   out_2571791232745662537[221] = 0.0;
   out_2571791232745662537[222] = 0.0;
   out_2571791232745662537[223] = 0.0;
   out_2571791232745662537[224] = 0.0;
   out_2571791232745662537[225] = 0.0;
   out_2571791232745662537[226] = 0.0;
   out_2571791232745662537[227] = 0.0;
   out_2571791232745662537[228] = 1.0;
   out_2571791232745662537[229] = 0.0;
   out_2571791232745662537[230] = 0.0;
   out_2571791232745662537[231] = 0.0;
   out_2571791232745662537[232] = 0.0;
   out_2571791232745662537[233] = 0.0;
   out_2571791232745662537[234] = 0.0;
   out_2571791232745662537[235] = 0.0;
   out_2571791232745662537[236] = 0.0;
   out_2571791232745662537[237] = 0.0;
   out_2571791232745662537[238] = 0.0;
   out_2571791232745662537[239] = 0.0;
   out_2571791232745662537[240] = 0.0;
   out_2571791232745662537[241] = 0.0;
   out_2571791232745662537[242] = 0.0;
   out_2571791232745662537[243] = 0.0;
   out_2571791232745662537[244] = 0.0;
   out_2571791232745662537[245] = 0.0;
   out_2571791232745662537[246] = 0.0;
   out_2571791232745662537[247] = 1.0;
   out_2571791232745662537[248] = 0.0;
   out_2571791232745662537[249] = 0.0;
   out_2571791232745662537[250] = 0.0;
   out_2571791232745662537[251] = 0.0;
   out_2571791232745662537[252] = 0.0;
   out_2571791232745662537[253] = 0.0;
   out_2571791232745662537[254] = 0.0;
   out_2571791232745662537[255] = 0.0;
   out_2571791232745662537[256] = 0.0;
   out_2571791232745662537[257] = 0.0;
   out_2571791232745662537[258] = 0.0;
   out_2571791232745662537[259] = 0.0;
   out_2571791232745662537[260] = 0.0;
   out_2571791232745662537[261] = 0.0;
   out_2571791232745662537[262] = 0.0;
   out_2571791232745662537[263] = 0.0;
   out_2571791232745662537[264] = 0.0;
   out_2571791232745662537[265] = 0.0;
   out_2571791232745662537[266] = 1.0;
   out_2571791232745662537[267] = 0.0;
   out_2571791232745662537[268] = 0.0;
   out_2571791232745662537[269] = 0.0;
   out_2571791232745662537[270] = 0.0;
   out_2571791232745662537[271] = 0.0;
   out_2571791232745662537[272] = 0.0;
   out_2571791232745662537[273] = 0.0;
   out_2571791232745662537[274] = 0.0;
   out_2571791232745662537[275] = 0.0;
   out_2571791232745662537[276] = 0.0;
   out_2571791232745662537[277] = 0.0;
   out_2571791232745662537[278] = 0.0;
   out_2571791232745662537[279] = 0.0;
   out_2571791232745662537[280] = 0.0;
   out_2571791232745662537[281] = 0.0;
   out_2571791232745662537[282] = 0.0;
   out_2571791232745662537[283] = 0.0;
   out_2571791232745662537[284] = 0.0;
   out_2571791232745662537[285] = 1.0;
   out_2571791232745662537[286] = 0.0;
   out_2571791232745662537[287] = 0.0;
   out_2571791232745662537[288] = 0.0;
   out_2571791232745662537[289] = 0.0;
   out_2571791232745662537[290] = 0.0;
   out_2571791232745662537[291] = 0.0;
   out_2571791232745662537[292] = 0.0;
   out_2571791232745662537[293] = 0.0;
   out_2571791232745662537[294] = 0.0;
   out_2571791232745662537[295] = 0.0;
   out_2571791232745662537[296] = 0.0;
   out_2571791232745662537[297] = 0.0;
   out_2571791232745662537[298] = 0.0;
   out_2571791232745662537[299] = 0.0;
   out_2571791232745662537[300] = 0.0;
   out_2571791232745662537[301] = 0.0;
   out_2571791232745662537[302] = 0.0;
   out_2571791232745662537[303] = 0.0;
   out_2571791232745662537[304] = 1.0;
   out_2571791232745662537[305] = 0.0;
   out_2571791232745662537[306] = 0.0;
   out_2571791232745662537[307] = 0.0;
   out_2571791232745662537[308] = 0.0;
   out_2571791232745662537[309] = 0.0;
   out_2571791232745662537[310] = 0.0;
   out_2571791232745662537[311] = 0.0;
   out_2571791232745662537[312] = 0.0;
   out_2571791232745662537[313] = 0.0;
   out_2571791232745662537[314] = 0.0;
   out_2571791232745662537[315] = 0.0;
   out_2571791232745662537[316] = 0.0;
   out_2571791232745662537[317] = 0.0;
   out_2571791232745662537[318] = 0.0;
   out_2571791232745662537[319] = 0.0;
   out_2571791232745662537[320] = 0.0;
   out_2571791232745662537[321] = 0.0;
   out_2571791232745662537[322] = 0.0;
   out_2571791232745662537[323] = 1.0;
}
void f_fun(double *state, double dt, double *out_5926050354811860597) {
   out_5926050354811860597[0] = atan2((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), -(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]));
   out_5926050354811860597[1] = asin(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]));
   out_5926050354811860597[2] = atan2(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), -(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]));
   out_5926050354811860597[3] = dt*state[12] + state[3];
   out_5926050354811860597[4] = dt*state[13] + state[4];
   out_5926050354811860597[5] = dt*state[14] + state[5];
   out_5926050354811860597[6] = state[6];
   out_5926050354811860597[7] = state[7];
   out_5926050354811860597[8] = state[8];
   out_5926050354811860597[9] = state[9];
   out_5926050354811860597[10] = state[10];
   out_5926050354811860597[11] = state[11];
   out_5926050354811860597[12] = state[12];
   out_5926050354811860597[13] = state[13];
   out_5926050354811860597[14] = state[14];
   out_5926050354811860597[15] = state[15];
   out_5926050354811860597[16] = state[16];
   out_5926050354811860597[17] = state[17];
}
void F_fun(double *state, double dt, double *out_7827254057592880210) {
   out_7827254057592880210[0] = ((-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*cos(state[0])*cos(state[1]) - sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*cos(state[0])*cos(state[1]) - sin(dt*state[6])*sin(state[0])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7827254057592880210[1] = ((-sin(dt*state[6])*sin(dt*state[8]) - sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*cos(state[1]) - (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*sin(state[1]) - sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(state[0]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*sin(state[1]) + (-sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) + sin(dt*state[8])*cos(dt*state[6]))*cos(state[1]) - sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(state[0]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7827254057592880210[2] = 0;
   out_7827254057592880210[3] = 0;
   out_7827254057592880210[4] = 0;
   out_7827254057592880210[5] = 0;
   out_7827254057592880210[6] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(dt*cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) - dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7827254057592880210[7] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*sin(dt*state[7])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[6])*sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) - dt*sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[7])*cos(dt*state[6])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[8])*sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]) - dt*sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7827254057592880210[8] = ((dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((dt*sin(dt*state[6])*sin(dt*state[8]) + dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_7827254057592880210[9] = 0;
   out_7827254057592880210[10] = 0;
   out_7827254057592880210[11] = 0;
   out_7827254057592880210[12] = 0;
   out_7827254057592880210[13] = 0;
   out_7827254057592880210[14] = 0;
   out_7827254057592880210[15] = 0;
   out_7827254057592880210[16] = 0;
   out_7827254057592880210[17] = 0;
   out_7827254057592880210[18] = (-sin(dt*state[7])*sin(state[0])*cos(state[1]) - sin(dt*state[8])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7827254057592880210[19] = (-sin(dt*state[7])*sin(state[1])*cos(state[0]) + sin(dt*state[8])*sin(state[0])*sin(state[1])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7827254057592880210[20] = 0;
   out_7827254057592880210[21] = 0;
   out_7827254057592880210[22] = 0;
   out_7827254057592880210[23] = 0;
   out_7827254057592880210[24] = 0;
   out_7827254057592880210[25] = (dt*sin(dt*state[7])*sin(dt*state[8])*sin(state[0])*cos(state[1]) - dt*sin(dt*state[7])*sin(state[1])*cos(dt*state[8]) + dt*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7827254057592880210[26] = (-dt*sin(dt*state[8])*sin(state[1])*cos(dt*state[7]) - dt*sin(state[0])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_7827254057592880210[27] = 0;
   out_7827254057592880210[28] = 0;
   out_7827254057592880210[29] = 0;
   out_7827254057592880210[30] = 0;
   out_7827254057592880210[31] = 0;
   out_7827254057592880210[32] = 0;
   out_7827254057592880210[33] = 0;
   out_7827254057592880210[34] = 0;
   out_7827254057592880210[35] = 0;
   out_7827254057592880210[36] = ((sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7827254057592880210[37] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-sin(dt*state[7])*sin(state[2])*cos(state[0])*cos(state[1]) + sin(dt*state[8])*sin(state[0])*sin(state[2])*cos(dt*state[7])*cos(state[1]) - sin(state[1])*sin(state[2])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(-sin(dt*state[7])*cos(state[0])*cos(state[1])*cos(state[2]) + sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1])*cos(state[2]) - sin(state[1])*cos(dt*state[7])*cos(dt*state[8])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7827254057592880210[38] = ((-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (-sin(state[0])*sin(state[1])*sin(state[2]) - cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7827254057592880210[39] = 0;
   out_7827254057592880210[40] = 0;
   out_7827254057592880210[41] = 0;
   out_7827254057592880210[42] = 0;
   out_7827254057592880210[43] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(dt*(sin(state[0])*cos(state[2]) - sin(state[1])*sin(state[2])*cos(state[0]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*sin(state[2])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(dt*(-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7827254057592880210[44] = (dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*sin(state[2])*cos(dt*state[7])*cos(state[1]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + (dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[7])*cos(state[1])*cos(state[2]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_7827254057592880210[45] = 0;
   out_7827254057592880210[46] = 0;
   out_7827254057592880210[47] = 0;
   out_7827254057592880210[48] = 0;
   out_7827254057592880210[49] = 0;
   out_7827254057592880210[50] = 0;
   out_7827254057592880210[51] = 0;
   out_7827254057592880210[52] = 0;
   out_7827254057592880210[53] = 0;
   out_7827254057592880210[54] = 0;
   out_7827254057592880210[55] = 0;
   out_7827254057592880210[56] = 0;
   out_7827254057592880210[57] = 1;
   out_7827254057592880210[58] = 0;
   out_7827254057592880210[59] = 0;
   out_7827254057592880210[60] = 0;
   out_7827254057592880210[61] = 0;
   out_7827254057592880210[62] = 0;
   out_7827254057592880210[63] = 0;
   out_7827254057592880210[64] = 0;
   out_7827254057592880210[65] = 0;
   out_7827254057592880210[66] = dt;
   out_7827254057592880210[67] = 0;
   out_7827254057592880210[68] = 0;
   out_7827254057592880210[69] = 0;
   out_7827254057592880210[70] = 0;
   out_7827254057592880210[71] = 0;
   out_7827254057592880210[72] = 0;
   out_7827254057592880210[73] = 0;
   out_7827254057592880210[74] = 0;
   out_7827254057592880210[75] = 0;
   out_7827254057592880210[76] = 1;
   out_7827254057592880210[77] = 0;
   out_7827254057592880210[78] = 0;
   out_7827254057592880210[79] = 0;
   out_7827254057592880210[80] = 0;
   out_7827254057592880210[81] = 0;
   out_7827254057592880210[82] = 0;
   out_7827254057592880210[83] = 0;
   out_7827254057592880210[84] = 0;
   out_7827254057592880210[85] = dt;
   out_7827254057592880210[86] = 0;
   out_7827254057592880210[87] = 0;
   out_7827254057592880210[88] = 0;
   out_7827254057592880210[89] = 0;
   out_7827254057592880210[90] = 0;
   out_7827254057592880210[91] = 0;
   out_7827254057592880210[92] = 0;
   out_7827254057592880210[93] = 0;
   out_7827254057592880210[94] = 0;
   out_7827254057592880210[95] = 1;
   out_7827254057592880210[96] = 0;
   out_7827254057592880210[97] = 0;
   out_7827254057592880210[98] = 0;
   out_7827254057592880210[99] = 0;
   out_7827254057592880210[100] = 0;
   out_7827254057592880210[101] = 0;
   out_7827254057592880210[102] = 0;
   out_7827254057592880210[103] = 0;
   out_7827254057592880210[104] = dt;
   out_7827254057592880210[105] = 0;
   out_7827254057592880210[106] = 0;
   out_7827254057592880210[107] = 0;
   out_7827254057592880210[108] = 0;
   out_7827254057592880210[109] = 0;
   out_7827254057592880210[110] = 0;
   out_7827254057592880210[111] = 0;
   out_7827254057592880210[112] = 0;
   out_7827254057592880210[113] = 0;
   out_7827254057592880210[114] = 1;
   out_7827254057592880210[115] = 0;
   out_7827254057592880210[116] = 0;
   out_7827254057592880210[117] = 0;
   out_7827254057592880210[118] = 0;
   out_7827254057592880210[119] = 0;
   out_7827254057592880210[120] = 0;
   out_7827254057592880210[121] = 0;
   out_7827254057592880210[122] = 0;
   out_7827254057592880210[123] = 0;
   out_7827254057592880210[124] = 0;
   out_7827254057592880210[125] = 0;
   out_7827254057592880210[126] = 0;
   out_7827254057592880210[127] = 0;
   out_7827254057592880210[128] = 0;
   out_7827254057592880210[129] = 0;
   out_7827254057592880210[130] = 0;
   out_7827254057592880210[131] = 0;
   out_7827254057592880210[132] = 0;
   out_7827254057592880210[133] = 1;
   out_7827254057592880210[134] = 0;
   out_7827254057592880210[135] = 0;
   out_7827254057592880210[136] = 0;
   out_7827254057592880210[137] = 0;
   out_7827254057592880210[138] = 0;
   out_7827254057592880210[139] = 0;
   out_7827254057592880210[140] = 0;
   out_7827254057592880210[141] = 0;
   out_7827254057592880210[142] = 0;
   out_7827254057592880210[143] = 0;
   out_7827254057592880210[144] = 0;
   out_7827254057592880210[145] = 0;
   out_7827254057592880210[146] = 0;
   out_7827254057592880210[147] = 0;
   out_7827254057592880210[148] = 0;
   out_7827254057592880210[149] = 0;
   out_7827254057592880210[150] = 0;
   out_7827254057592880210[151] = 0;
   out_7827254057592880210[152] = 1;
   out_7827254057592880210[153] = 0;
   out_7827254057592880210[154] = 0;
   out_7827254057592880210[155] = 0;
   out_7827254057592880210[156] = 0;
   out_7827254057592880210[157] = 0;
   out_7827254057592880210[158] = 0;
   out_7827254057592880210[159] = 0;
   out_7827254057592880210[160] = 0;
   out_7827254057592880210[161] = 0;
   out_7827254057592880210[162] = 0;
   out_7827254057592880210[163] = 0;
   out_7827254057592880210[164] = 0;
   out_7827254057592880210[165] = 0;
   out_7827254057592880210[166] = 0;
   out_7827254057592880210[167] = 0;
   out_7827254057592880210[168] = 0;
   out_7827254057592880210[169] = 0;
   out_7827254057592880210[170] = 0;
   out_7827254057592880210[171] = 1;
   out_7827254057592880210[172] = 0;
   out_7827254057592880210[173] = 0;
   out_7827254057592880210[174] = 0;
   out_7827254057592880210[175] = 0;
   out_7827254057592880210[176] = 0;
   out_7827254057592880210[177] = 0;
   out_7827254057592880210[178] = 0;
   out_7827254057592880210[179] = 0;
   out_7827254057592880210[180] = 0;
   out_7827254057592880210[181] = 0;
   out_7827254057592880210[182] = 0;
   out_7827254057592880210[183] = 0;
   out_7827254057592880210[184] = 0;
   out_7827254057592880210[185] = 0;
   out_7827254057592880210[186] = 0;
   out_7827254057592880210[187] = 0;
   out_7827254057592880210[188] = 0;
   out_7827254057592880210[189] = 0;
   out_7827254057592880210[190] = 1;
   out_7827254057592880210[191] = 0;
   out_7827254057592880210[192] = 0;
   out_7827254057592880210[193] = 0;
   out_7827254057592880210[194] = 0;
   out_7827254057592880210[195] = 0;
   out_7827254057592880210[196] = 0;
   out_7827254057592880210[197] = 0;
   out_7827254057592880210[198] = 0;
   out_7827254057592880210[199] = 0;
   out_7827254057592880210[200] = 0;
   out_7827254057592880210[201] = 0;
   out_7827254057592880210[202] = 0;
   out_7827254057592880210[203] = 0;
   out_7827254057592880210[204] = 0;
   out_7827254057592880210[205] = 0;
   out_7827254057592880210[206] = 0;
   out_7827254057592880210[207] = 0;
   out_7827254057592880210[208] = 0;
   out_7827254057592880210[209] = 1;
   out_7827254057592880210[210] = 0;
   out_7827254057592880210[211] = 0;
   out_7827254057592880210[212] = 0;
   out_7827254057592880210[213] = 0;
   out_7827254057592880210[214] = 0;
   out_7827254057592880210[215] = 0;
   out_7827254057592880210[216] = 0;
   out_7827254057592880210[217] = 0;
   out_7827254057592880210[218] = 0;
   out_7827254057592880210[219] = 0;
   out_7827254057592880210[220] = 0;
   out_7827254057592880210[221] = 0;
   out_7827254057592880210[222] = 0;
   out_7827254057592880210[223] = 0;
   out_7827254057592880210[224] = 0;
   out_7827254057592880210[225] = 0;
   out_7827254057592880210[226] = 0;
   out_7827254057592880210[227] = 0;
   out_7827254057592880210[228] = 1;
   out_7827254057592880210[229] = 0;
   out_7827254057592880210[230] = 0;
   out_7827254057592880210[231] = 0;
   out_7827254057592880210[232] = 0;
   out_7827254057592880210[233] = 0;
   out_7827254057592880210[234] = 0;
   out_7827254057592880210[235] = 0;
   out_7827254057592880210[236] = 0;
   out_7827254057592880210[237] = 0;
   out_7827254057592880210[238] = 0;
   out_7827254057592880210[239] = 0;
   out_7827254057592880210[240] = 0;
   out_7827254057592880210[241] = 0;
   out_7827254057592880210[242] = 0;
   out_7827254057592880210[243] = 0;
   out_7827254057592880210[244] = 0;
   out_7827254057592880210[245] = 0;
   out_7827254057592880210[246] = 0;
   out_7827254057592880210[247] = 1;
   out_7827254057592880210[248] = 0;
   out_7827254057592880210[249] = 0;
   out_7827254057592880210[250] = 0;
   out_7827254057592880210[251] = 0;
   out_7827254057592880210[252] = 0;
   out_7827254057592880210[253] = 0;
   out_7827254057592880210[254] = 0;
   out_7827254057592880210[255] = 0;
   out_7827254057592880210[256] = 0;
   out_7827254057592880210[257] = 0;
   out_7827254057592880210[258] = 0;
   out_7827254057592880210[259] = 0;
   out_7827254057592880210[260] = 0;
   out_7827254057592880210[261] = 0;
   out_7827254057592880210[262] = 0;
   out_7827254057592880210[263] = 0;
   out_7827254057592880210[264] = 0;
   out_7827254057592880210[265] = 0;
   out_7827254057592880210[266] = 1;
   out_7827254057592880210[267] = 0;
   out_7827254057592880210[268] = 0;
   out_7827254057592880210[269] = 0;
   out_7827254057592880210[270] = 0;
   out_7827254057592880210[271] = 0;
   out_7827254057592880210[272] = 0;
   out_7827254057592880210[273] = 0;
   out_7827254057592880210[274] = 0;
   out_7827254057592880210[275] = 0;
   out_7827254057592880210[276] = 0;
   out_7827254057592880210[277] = 0;
   out_7827254057592880210[278] = 0;
   out_7827254057592880210[279] = 0;
   out_7827254057592880210[280] = 0;
   out_7827254057592880210[281] = 0;
   out_7827254057592880210[282] = 0;
   out_7827254057592880210[283] = 0;
   out_7827254057592880210[284] = 0;
   out_7827254057592880210[285] = 1;
   out_7827254057592880210[286] = 0;
   out_7827254057592880210[287] = 0;
   out_7827254057592880210[288] = 0;
   out_7827254057592880210[289] = 0;
   out_7827254057592880210[290] = 0;
   out_7827254057592880210[291] = 0;
   out_7827254057592880210[292] = 0;
   out_7827254057592880210[293] = 0;
   out_7827254057592880210[294] = 0;
   out_7827254057592880210[295] = 0;
   out_7827254057592880210[296] = 0;
   out_7827254057592880210[297] = 0;
   out_7827254057592880210[298] = 0;
   out_7827254057592880210[299] = 0;
   out_7827254057592880210[300] = 0;
   out_7827254057592880210[301] = 0;
   out_7827254057592880210[302] = 0;
   out_7827254057592880210[303] = 0;
   out_7827254057592880210[304] = 1;
   out_7827254057592880210[305] = 0;
   out_7827254057592880210[306] = 0;
   out_7827254057592880210[307] = 0;
   out_7827254057592880210[308] = 0;
   out_7827254057592880210[309] = 0;
   out_7827254057592880210[310] = 0;
   out_7827254057592880210[311] = 0;
   out_7827254057592880210[312] = 0;
   out_7827254057592880210[313] = 0;
   out_7827254057592880210[314] = 0;
   out_7827254057592880210[315] = 0;
   out_7827254057592880210[316] = 0;
   out_7827254057592880210[317] = 0;
   out_7827254057592880210[318] = 0;
   out_7827254057592880210[319] = 0;
   out_7827254057592880210[320] = 0;
   out_7827254057592880210[321] = 0;
   out_7827254057592880210[322] = 0;
   out_7827254057592880210[323] = 1;
}
void h_4(double *state, double *unused, double *out_7267195365920089452) {
   out_7267195365920089452[0] = state[6] + state[9];
   out_7267195365920089452[1] = state[7] + state[10];
   out_7267195365920089452[2] = state[8] + state[11];
}
void H_4(double *state, double *unused, double *out_3325952234800375144) {
   out_3325952234800375144[0] = 0;
   out_3325952234800375144[1] = 0;
   out_3325952234800375144[2] = 0;
   out_3325952234800375144[3] = 0;
   out_3325952234800375144[4] = 0;
   out_3325952234800375144[5] = 0;
   out_3325952234800375144[6] = 1;
   out_3325952234800375144[7] = 0;
   out_3325952234800375144[8] = 0;
   out_3325952234800375144[9] = 1;
   out_3325952234800375144[10] = 0;
   out_3325952234800375144[11] = 0;
   out_3325952234800375144[12] = 0;
   out_3325952234800375144[13] = 0;
   out_3325952234800375144[14] = 0;
   out_3325952234800375144[15] = 0;
   out_3325952234800375144[16] = 0;
   out_3325952234800375144[17] = 0;
   out_3325952234800375144[18] = 0;
   out_3325952234800375144[19] = 0;
   out_3325952234800375144[20] = 0;
   out_3325952234800375144[21] = 0;
   out_3325952234800375144[22] = 0;
   out_3325952234800375144[23] = 0;
   out_3325952234800375144[24] = 0;
   out_3325952234800375144[25] = 1;
   out_3325952234800375144[26] = 0;
   out_3325952234800375144[27] = 0;
   out_3325952234800375144[28] = 1;
   out_3325952234800375144[29] = 0;
   out_3325952234800375144[30] = 0;
   out_3325952234800375144[31] = 0;
   out_3325952234800375144[32] = 0;
   out_3325952234800375144[33] = 0;
   out_3325952234800375144[34] = 0;
   out_3325952234800375144[35] = 0;
   out_3325952234800375144[36] = 0;
   out_3325952234800375144[37] = 0;
   out_3325952234800375144[38] = 0;
   out_3325952234800375144[39] = 0;
   out_3325952234800375144[40] = 0;
   out_3325952234800375144[41] = 0;
   out_3325952234800375144[42] = 0;
   out_3325952234800375144[43] = 0;
   out_3325952234800375144[44] = 1;
   out_3325952234800375144[45] = 0;
   out_3325952234800375144[46] = 0;
   out_3325952234800375144[47] = 1;
   out_3325952234800375144[48] = 0;
   out_3325952234800375144[49] = 0;
   out_3325952234800375144[50] = 0;
   out_3325952234800375144[51] = 0;
   out_3325952234800375144[52] = 0;
   out_3325952234800375144[53] = 0;
}
void h_10(double *state, double *unused, double *out_2780660147189760244) {
   out_2780660147189760244[0] = 9.8100000000000005*sin(state[1]) - state[4]*state[8] + state[5]*state[7] + state[12] + state[15];
   out_2780660147189760244[1] = -9.8100000000000005*sin(state[0])*cos(state[1]) + state[3]*state[8] - state[5]*state[6] + state[13] + state[16];
   out_2780660147189760244[2] = -9.8100000000000005*cos(state[0])*cos(state[1]) - state[3]*state[7] + state[4]*state[6] + state[14] + state[17];
}
void H_10(double *state, double *unused, double *out_3376480556476068541) {
   out_3376480556476068541[0] = 0;
   out_3376480556476068541[1] = 9.8100000000000005*cos(state[1]);
   out_3376480556476068541[2] = 0;
   out_3376480556476068541[3] = 0;
   out_3376480556476068541[4] = -state[8];
   out_3376480556476068541[5] = state[7];
   out_3376480556476068541[6] = 0;
   out_3376480556476068541[7] = state[5];
   out_3376480556476068541[8] = -state[4];
   out_3376480556476068541[9] = 0;
   out_3376480556476068541[10] = 0;
   out_3376480556476068541[11] = 0;
   out_3376480556476068541[12] = 1;
   out_3376480556476068541[13] = 0;
   out_3376480556476068541[14] = 0;
   out_3376480556476068541[15] = 1;
   out_3376480556476068541[16] = 0;
   out_3376480556476068541[17] = 0;
   out_3376480556476068541[18] = -9.8100000000000005*cos(state[0])*cos(state[1]);
   out_3376480556476068541[19] = 9.8100000000000005*sin(state[0])*sin(state[1]);
   out_3376480556476068541[20] = 0;
   out_3376480556476068541[21] = state[8];
   out_3376480556476068541[22] = 0;
   out_3376480556476068541[23] = -state[6];
   out_3376480556476068541[24] = -state[5];
   out_3376480556476068541[25] = 0;
   out_3376480556476068541[26] = state[3];
   out_3376480556476068541[27] = 0;
   out_3376480556476068541[28] = 0;
   out_3376480556476068541[29] = 0;
   out_3376480556476068541[30] = 0;
   out_3376480556476068541[31] = 1;
   out_3376480556476068541[32] = 0;
   out_3376480556476068541[33] = 0;
   out_3376480556476068541[34] = 1;
   out_3376480556476068541[35] = 0;
   out_3376480556476068541[36] = 9.8100000000000005*sin(state[0])*cos(state[1]);
   out_3376480556476068541[37] = 9.8100000000000005*sin(state[1])*cos(state[0]);
   out_3376480556476068541[38] = 0;
   out_3376480556476068541[39] = -state[7];
   out_3376480556476068541[40] = state[6];
   out_3376480556476068541[41] = 0;
   out_3376480556476068541[42] = state[4];
   out_3376480556476068541[43] = -state[3];
   out_3376480556476068541[44] = 0;
   out_3376480556476068541[45] = 0;
   out_3376480556476068541[46] = 0;
   out_3376480556476068541[47] = 0;
   out_3376480556476068541[48] = 0;
   out_3376480556476068541[49] = 0;
   out_3376480556476068541[50] = 1;
   out_3376480556476068541[51] = 0;
   out_3376480556476068541[52] = 0;
   out_3376480556476068541[53] = 1;
}
void h_13(double *state, double *unused, double *out_621962457486468118) {
   out_621962457486468118[0] = state[3];
   out_621962457486468118[1] = state[4];
   out_621962457486468118[2] = state[5];
}
void H_13(double *state, double *unused, double *out_7510160630592475543) {
   out_7510160630592475543[0] = 0;
   out_7510160630592475543[1] = 0;
   out_7510160630592475543[2] = 0;
   out_7510160630592475543[3] = 1;
   out_7510160630592475543[4] = 0;
   out_7510160630592475543[5] = 0;
   out_7510160630592475543[6] = 0;
   out_7510160630592475543[7] = 0;
   out_7510160630592475543[8] = 0;
   out_7510160630592475543[9] = 0;
   out_7510160630592475543[10] = 0;
   out_7510160630592475543[11] = 0;
   out_7510160630592475543[12] = 0;
   out_7510160630592475543[13] = 0;
   out_7510160630592475543[14] = 0;
   out_7510160630592475543[15] = 0;
   out_7510160630592475543[16] = 0;
   out_7510160630592475543[17] = 0;
   out_7510160630592475543[18] = 0;
   out_7510160630592475543[19] = 0;
   out_7510160630592475543[20] = 0;
   out_7510160630592475543[21] = 0;
   out_7510160630592475543[22] = 1;
   out_7510160630592475543[23] = 0;
   out_7510160630592475543[24] = 0;
   out_7510160630592475543[25] = 0;
   out_7510160630592475543[26] = 0;
   out_7510160630592475543[27] = 0;
   out_7510160630592475543[28] = 0;
   out_7510160630592475543[29] = 0;
   out_7510160630592475543[30] = 0;
   out_7510160630592475543[31] = 0;
   out_7510160630592475543[32] = 0;
   out_7510160630592475543[33] = 0;
   out_7510160630592475543[34] = 0;
   out_7510160630592475543[35] = 0;
   out_7510160630592475543[36] = 0;
   out_7510160630592475543[37] = 0;
   out_7510160630592475543[38] = 0;
   out_7510160630592475543[39] = 0;
   out_7510160630592475543[40] = 0;
   out_7510160630592475543[41] = 1;
   out_7510160630592475543[42] = 0;
   out_7510160630592475543[43] = 0;
   out_7510160630592475543[44] = 0;
   out_7510160630592475543[45] = 0;
   out_7510160630592475543[46] = 0;
   out_7510160630592475543[47] = 0;
   out_7510160630592475543[48] = 0;
   out_7510160630592475543[49] = 0;
   out_7510160630592475543[50] = 0;
   out_7510160630592475543[51] = 0;
   out_7510160630592475543[52] = 0;
   out_7510160630592475543[53] = 0;
}
void h_14(double *state, double *unused, double *out_1217207074346016783) {
   out_1217207074346016783[0] = state[6];
   out_1217207074346016783[1] = state[7];
   out_1217207074346016783[2] = state[8];
}
void H_14(double *state, double *unused, double *out_7289193091139859673) {
   out_7289193091139859673[0] = 0;
   out_7289193091139859673[1] = 0;
   out_7289193091139859673[2] = 0;
   out_7289193091139859673[3] = 0;
   out_7289193091139859673[4] = 0;
   out_7289193091139859673[5] = 0;
   out_7289193091139859673[6] = 1;
   out_7289193091139859673[7] = 0;
   out_7289193091139859673[8] = 0;
   out_7289193091139859673[9] = 0;
   out_7289193091139859673[10] = 0;
   out_7289193091139859673[11] = 0;
   out_7289193091139859673[12] = 0;
   out_7289193091139859673[13] = 0;
   out_7289193091139859673[14] = 0;
   out_7289193091139859673[15] = 0;
   out_7289193091139859673[16] = 0;
   out_7289193091139859673[17] = 0;
   out_7289193091139859673[18] = 0;
   out_7289193091139859673[19] = 0;
   out_7289193091139859673[20] = 0;
   out_7289193091139859673[21] = 0;
   out_7289193091139859673[22] = 0;
   out_7289193091139859673[23] = 0;
   out_7289193091139859673[24] = 0;
   out_7289193091139859673[25] = 1;
   out_7289193091139859673[26] = 0;
   out_7289193091139859673[27] = 0;
   out_7289193091139859673[28] = 0;
   out_7289193091139859673[29] = 0;
   out_7289193091139859673[30] = 0;
   out_7289193091139859673[31] = 0;
   out_7289193091139859673[32] = 0;
   out_7289193091139859673[33] = 0;
   out_7289193091139859673[34] = 0;
   out_7289193091139859673[35] = 0;
   out_7289193091139859673[36] = 0;
   out_7289193091139859673[37] = 0;
   out_7289193091139859673[38] = 0;
   out_7289193091139859673[39] = 0;
   out_7289193091139859673[40] = 0;
   out_7289193091139859673[41] = 0;
   out_7289193091139859673[42] = 0;
   out_7289193091139859673[43] = 0;
   out_7289193091139859673[44] = 1;
   out_7289193091139859673[45] = 0;
   out_7289193091139859673[46] = 0;
   out_7289193091139859673[47] = 0;
   out_7289193091139859673[48] = 0;
   out_7289193091139859673[49] = 0;
   out_7289193091139859673[50] = 0;
   out_7289193091139859673[51] = 0;
   out_7289193091139859673[52] = 0;
   out_7289193091139859673[53] = 0;
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
void pose_err_fun(double *nom_x, double *delta_x, double *out_431546898630699983) {
  err_fun(nom_x, delta_x, out_431546898630699983);
}
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_3139108192969388081) {
  inv_err_fun(nom_x, true_x, out_3139108192969388081);
}
void pose_H_mod_fun(double *state, double *out_2571791232745662537) {
  H_mod_fun(state, out_2571791232745662537);
}
void pose_f_fun(double *state, double dt, double *out_5926050354811860597) {
  f_fun(state,  dt, out_5926050354811860597);
}
void pose_F_fun(double *state, double dt, double *out_7827254057592880210) {
  F_fun(state,  dt, out_7827254057592880210);
}
void pose_h_4(double *state, double *unused, double *out_7267195365920089452) {
  h_4(state, unused, out_7267195365920089452);
}
void pose_H_4(double *state, double *unused, double *out_3325952234800375144) {
  H_4(state, unused, out_3325952234800375144);
}
void pose_h_10(double *state, double *unused, double *out_2780660147189760244) {
  h_10(state, unused, out_2780660147189760244);
}
void pose_H_10(double *state, double *unused, double *out_3376480556476068541) {
  H_10(state, unused, out_3376480556476068541);
}
void pose_h_13(double *state, double *unused, double *out_621962457486468118) {
  h_13(state, unused, out_621962457486468118);
}
void pose_H_13(double *state, double *unused, double *out_7510160630592475543) {
  H_13(state, unused, out_7510160630592475543);
}
void pose_h_14(double *state, double *unused, double *out_1217207074346016783) {
  h_14(state, unused, out_1217207074346016783);
}
void pose_H_14(double *state, double *unused, double *out_7289193091139859673) {
  H_14(state, unused, out_7289193091139859673);
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
