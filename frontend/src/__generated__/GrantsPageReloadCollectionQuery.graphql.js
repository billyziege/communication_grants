/**
 * @generated SignedSource<<83ec3685a920362ca625711b91170e1b>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* eslint-disable */

'use strict';

var node = (function(){
var v0 = [
  {
    "defaultValue": null,
    "kind": "LocalArgument",
    "name": "items"
  }
],
v1 = [
  {
    "alias": null,
    "args": [
      {
        "kind": "Variable",
        "name": "items",
        "variableName": "items"
      }
    ],
    "concreteType": "GrantNode",
    "kind": "LinkedField",
    "name": "grantsBySource",
    "plural": true,
    "selections": [
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "id",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "title",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "organization",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "country",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "source",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "sourceId",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "sourceProgramme",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "sourceUrl",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "startDate",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "endDate",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "fundingAmount",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "fundingCurrency",
        "storageKey": null
      }
    ],
    "storageKey": null
  }
];
return {
  "fragment": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Fragment",
    "metadata": null,
    "name": "GrantsPageReloadCollectionQuery",
    "selections": (v1/*: any*/),
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "GrantsPageReloadCollectionQuery",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "5f27cee631e7728e2d169978294764f3",
    "id": null,
    "metadata": {},
    "name": "GrantsPageReloadCollectionQuery",
    "operationKind": "query",
    "text": "query GrantsPageReloadCollectionQuery(\n  $items: [GrantLookupInput!]!\n) {\n  grantsBySource(items: $items) {\n    id\n    title\n    organization\n    country\n    source\n    sourceId\n    sourceProgramme\n    sourceUrl\n    startDate\n    endDate\n    fundingAmount\n    fundingCurrency\n  }\n}\n"
  }
};
})();

node.hash = "4d6a89022b8e6cc8859cc6ee153eb5fd";

export default node;
