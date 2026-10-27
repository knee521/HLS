#ifndef EXP3_NN_INFER_H
#define EXP3_NN_INFER_H
#include <ap_int.h>
typedef ap_uint<8> pixel_t;
typedef ap_int<8> weight_t;
typedef ap_int<32> score_t;
typedef ap_uint<4> digit_t;
digit_t nn_infer(const pixel_t image[784]);
#ifndef __SYNTHESIS__
extern int debug_logits[10];
#endif
#endif

