# -*- coding: utf-8 -*-

"""
***************************************************************************
    RandomSelectionWithinSubsets.py
    ---------------------
    Date                 : August 2012
    Copyright            : (C) 2012 by Victor Olaya
    Email                : volayaf at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
from builtins import range

__author__ = 'Victor Olaya'
__date__ = 'August 2012'
__copyright__ = '(C) 2012, Victor Olaya'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import random

from qgis.core import (QgsApplication,
                       QgsFeatureSink,
                       QgsProcessingUtils,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterField,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingOutputVectorLayer)
from collections import defaultdict
from processing.algs.qgis.QgisAlgorithm import QgisAlgorithm
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException


class RandomExtractWithinSubsets(QgisAlgorithm):

    INPUT = 'INPUT'
    METHOD = 'METHOD'
    NUMBER = 'NUMBER'
    FIELD = 'FIELD'
    OUTPUT = 'OUTPUT'

    def group(self):
        return self.tr('Vector selection tools')

    def __init__(self):
        super().__init__()
        self.methods = [self.tr('Number of selected features'),
                        self.tr('Percentage of selected features')]

        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT,
                                                              self.tr('Input layer')))

        self.addParameter(QgsProcessingParameterField(self.FIELD,
                                                      self.tr('ID field'), None, self.INPUT))

        self.addParameter(QgsProcessingParameterEnum(self.METHOD,
                                                     self.tr('Method'), self.methods, False, 0))

        self.addParameter(QgsProcessingParameterNumber(self.NUMBER,
                                                       self.tr('Number/percentage of selected features'), QgsProcessingParameterNumber.Integer,
                                                       10, False, 0.0, 999999999999.0))

        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr('Extracted (random stratified)')))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT, self.tr('Extracted (random stratified)')))

    def name(self):
        return 'randomextractwithinsubsets'

    def displayName(self):
        return self.tr('Random extract within subsets')

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        method = self.parameterAsEnum(parameters, self.METHOD, context)

        field = self.parameterAsString(parameters, self.FIELD, context)

        index = source.fields().lookupField(field)

        features = source.getFeatures()
        featureCount = source.featureCount()
        unique = source.uniqueValues(index)
        value = self.parameterAsInt(parameters, self.NUMBER, context)
        if method == 0:
            if value > featureCount:
                raise GeoAlgorithmExecutionException(
                    self.tr('Selected number is greater that feature count. '
                            'Choose lesser value and try again.'))
        else:
            if value > 100:
                raise GeoAlgorithmExecutionException(
                    self.tr("Percentage can't be greater than 100. Set "
                            "correct value and try again."))
            value = value / 100.0

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               source.fields(), source.wkbType(), source.sourceCrs())

        selran = []
        total = 100.0 / (featureCount * len(unique)) if featureCount else 1

        classes = defaultdict(list)
        for i, feature in enumerate(features):
            if feedback.isCanceled():
                break
            attrs = feature.attributes()
            classes[attrs[index]].append(feature)
            feedback.setProgress(int(i * total))

        for subset in classes.values():
            selValue = value if method != 1 else int(round(value * len(subset), 0))
            selran.extend(random.sample(subset, selValue))

        total = 100.0 / featureCount if featureCount else 1
        for (i, feat) in enumerate(selran):
            if feedback.isCanceled():
                break
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(i * total))
        return {self.OUTPUT: dest_id}
