# INLG-18
The repository for the INLG-18 paper: Learning to Flip the Bias of News Headlines.

The code and the following instructions are mainly from Shen's work: "Style Transfer from Non-Parallel Text by Cross-Alignment". Tianxiao Shen, Tao Lei, Regina Barzilay, and Tommi Jaakkola. NIPS 2017.

The only difference is we implemented the beam search algorithm to remove unknown tokens from the generated texts.

Please visit [here](https://github.com/shentianxiao/language-style-transfer) as well

## Data Format
Please name the corpora of two styles by "x.0" and "x.1" respectively, and use "x" to refer to them in options. Each file should consist of one sentence per line with tokens separated by a space.

The <code>data/news/</code> directory contains our bias news dataset.
Visit [here](https://webis.de/data/webis-bias-flipper-18.html) for more details.

<br>

## Quick Start
- To train a model, first create a <code>tmp/</code> folder (where the model and results will be saved), then go to the <code>code/</code> folder and run the following command:
```bash
python style_transfer.py --train ../data/news/LR+c.trainC --dev ../data/news/LR+c.dev --output ../tmp/LR+c.dev --vocab ../tmp/news+c2.vocab --model ../tmp/model.LR+c_match --min_count 3 --max_epochs 100 --batch_size 24 --beam 10 --learning_rate 0.001
```

- To test the model, run the following command:
```bash
python style_transfer.py --test ../data/news/LR+c.test --output ../tmp/LR+c.test --vocab ../tmp/news+c2.vocab --model ../tmp/model.LR+c2 --load_model true --beam 10 
```

- Check <code>code/options.py</code> for all running options.

<br>

## Dependencies
Python >= 2.7, TensorFlow 1.3.0
