from collections import Counter
import glob
import os

import bblfsh
from bblfsh.client import NonUTF8ContentException
import numpy
from sklearn.metrics import classification_report,confusion_matrix
from tqdm import tqdm

from lookout.core.api.service_data_pb2 import File
from lookout.style.format.features import FeatureExtractor, CLASSES
from lookout.style.format.model import FormatModel


def prepare_files(folder, client, language):
    files = []

    # collect filenames with full path
    filenames = glob.glob(folder, recursive=True)

    for file in tqdm(filenames):
        if not os.path.isfile(file):
            continue
        try:
            res = client.parse(file)
        except NonUTF8ContentException:
            # skip files that can't be parsed because of UTF-8 decoding errors.
            continue
        if res.status == 0 and res.language.lower() == language.lower():
            uast = res.uast
            path = file
            with open(file) as f:
                content = f.read().encode("utf-8")
            files.append(File(content=content, uast=uast, path=path))
    return files


def quality_report(args):
    client = bblfsh.BblfshClient(args.bblfsh)
    files = prepare_files(args.input, client, args.language)
    print("Number of files: %s" % (len(files)))

    fe = FeatureExtractor(language=args.language)
    X, y, nodes = fe.extract_features(files)

    analyzer = FormatModel().load(args.model)
    rules = analyzer._rules_by_lang[args.language]
    y_pred = rules.predict(X)

    target_names = [CLASSES[cls_ind] for cls_ind in numpy.unique(y)]
    print("Classification report:\n" + classification_report(y, y_pred, target_names=target_names))
    print("Confusion matrix:\n" + str(confusion_matrix(y, y_pred)))

    # sort files by mispredictions and print them
    file_mispred = []
    for gt, pred, vn in zip(y, y_pred, nodes):
        if gt != pred:
            file_mispred.append(vn.path)
    file_stat = Counter(file_mispred)

    to_show = file_stat.most_common()
    if args.n_files > 0:
        to_show = to_show[:args.n_files]

    print("Files with most errors:\n" + "\n".join(map(str, to_show)))
