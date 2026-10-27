#include "nn_infer.h"
#include "weights.h"

#ifndef __SYNTHESIS__
int debug_logits[10];
#endif

digit_t nn_infer(const pixel_t image[784]) {
#pragma HLS INTERFACE ap_ctrl_hs port=return
#pragma HLS INTERFACE ap_memory port=image
#pragma HLS RESOURCE variable=image core=RAM_1P latency=1
#pragma HLS RESOURCE variable=W1 core=ROM_1P_BRAM
#pragma HLS RESOURCE variable=W2 core=ROM_1P_BRAM
    pixel_t pixels[784];
    pixel_t hidden[32];
#pragma HLS RESOURCE variable=pixels core=RAM_1P_BRAM
#pragma HLS RESOURCE variable=hidden core=RAM_1P_LUTRAM
COPY_INPUT:
    for (int i = 0; i < 784; ++i) {
#pragma HLS PIPELINE II=1
        pixels[i] = image[i];
    }
HIDDEN_NODE:
    for (int j = 0; j < 32; ++j) {
        score_t sum = B1[j];
HIDDEN_MAC:
        for (int i = 0; i < 784; ++i) {
#ifndef EXP3_NO_PIPELINE
#pragma HLS PIPELINE II=1
#endif
            ap_int<9> value = pixels[i];
            ap_int<17> product = value * W1[j][i];
            sum += score_t(product);
        }
        ap_int<33> rounded = sum;
        if (rounded <= 0) hidden[j] = 0;
        else {
            if (REQUANT_SHIFT > 0) {
                rounded += ap_int<33>(1) << (REQUANT_SHIFT - 1);
                rounded >>= REQUANT_SHIFT;
            }
            hidden[j] = (rounded > 255) ? pixel_t(255) : pixel_t(rounded);
        }
    }
    digit_t winner = 0;
    score_t maximum = 0;
OUTPUT_NODE:
    for (int k = 0; k < 10; ++k) {
        score_t sum = B2[k];
OUTPUT_MAC:
        for (int j = 0; j < 32; ++j) {
#ifndef EXP3_NO_PIPELINE
#pragma HLS PIPELINE II=1
#endif
            ap_int<9> value = hidden[j];
            ap_int<17> product = value * W2[k][j];
            sum += score_t(product);
        }
#ifndef __SYNTHESIS__
        debug_logits[k] = sum.to_int();
#endif
        if (k == 0 || sum > maximum) {
            maximum = sum;
            winner = k;
        }
    }
    return winner;
}

